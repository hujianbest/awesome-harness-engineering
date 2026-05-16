"""F011 T4: pack_install module tests (FR-1106..1108 + INV-F11-5)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from garage_os.adapter.installer.pack_install import (
    PackInstallError,
    install_pack_from_url,
    list_installed_packs,
)


def _build_test_pack(repo_dir: Path, pack_id: str = "test-pack") -> None:
    """Build a minimal valid pack at repo_dir + git init."""
    (repo_dir / "skills" / "hello-skill").mkdir(parents=True)
    (repo_dir / "skills" / "hello-skill" / "SKILL.md").write_text(
        "---\nname: hello-skill\ndescription: minimal test skill\n---\n# Hello\n",
        encoding="utf-8",
    )
    (repo_dir / "pack.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pack_id": pack_id,
                "version": "0.1.0",
                "description": "Test pack for F011 install",
                "skills": ["hello-skill"],
                "agents": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (repo_dir / "README.md").write_text(f"# {pack_id}\n", encoding="utf-8")
    # git init + commit so it's a clonable repo
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
    subprocess.run(
        ["git", "-c", "user.email=test@test", "-c", "user.name=Test", "commit", "-q", "-m", "init"],
        cwd=repo_dir,
        check=True,
    )


class TestInstallPackFromUrl:
    def test_install_from_local_file_url(self, tmp_path: Path) -> None:
        # Build a test pack repo
        repo_dir = tmp_path / "src-pack"
        repo_dir.mkdir()
        _build_test_pack(repo_dir, pack_id="my-test-pack")

        # Install into a workspace
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        url = f"file://{repo_dir}"
        summary = install_pack_from_url(workspace, url)

        # Pack materialized
        installed = workspace / "packs" / "my-test-pack"
        assert installed.is_dir()
        assert (installed / "skills" / "hello-skill" / "SKILL.md").is_file()
        # source_url written
        pack_json = json.loads((installed / "pack.json").read_text())
        assert pack_json["source_url"] == url
        # Original fields preserved
        assert pack_json["pack_id"] == "my-test-pack"
        assert pack_json["version"] == "0.1.0"
        # Summary correct
        assert summary.pack_id == "my-test-pack"
        assert summary.source_url == url

    def test_install_existing_pack_raises(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "src-pack"
        repo_dir.mkdir()
        _build_test_pack(repo_dir, pack_id="dup-pack")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        url = f"file://{repo_dir}"
        install_pack_from_url(workspace, url)

        # Second install raises
        with pytest.raises(PackInstallError) as exc_info:
            install_pack_from_url(workspace, url)
        assert "already installed" in str(exc_info.value)

    def test_install_no_pack_json_raises(self, tmp_path: Path) -> None:
        # Build a repo without pack.json
        repo_dir = tmp_path / "bad-repo"
        repo_dir.mkdir()
        (repo_dir / "README.md").write_text("# Not a pack\n")
        subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=T", "commit", "-q", "-m", "init"],
            cwd=repo_dir,
            check=True,
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        url = f"file://{repo_dir}"
        with pytest.raises(PackInstallError) as exc_info:
            install_pack_from_url(workspace, url)
        assert "No pack.json" in str(exc_info.value)

    def test_install_invalid_url_raises(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        with pytest.raises(PackInstallError) as exc_info:
            install_pack_from_url(workspace, "https://nonexistent.invalid/pack.git")
        assert "git clone failed" in str(exc_info.value).lower() or "Could not resolve" in str(exc_info.value)


class TestListInstalledPacks:
    def test_empty_workspace_returns_empty(self, tmp_path: Path) -> None:
        assert list_installed_packs(tmp_path) == []

    def test_installed_pack_listed(self, tmp_path: Path) -> None:
        repo_dir = tmp_path / "src-pack"
        repo_dir.mkdir()
        _build_test_pack(repo_dir, pack_id="ls-test-pack")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        url = f"file://{repo_dir}"
        install_pack_from_url(workspace, url)

        listed = list_installed_packs(workspace)
        assert len(listed) == 1
        assert listed[0]["pack_id"] == "ls-test-pack"
        assert listed[0]["version"] == "0.1.0"
        assert listed[0]["source_url"] == url


class TestF007BackwardCompat:
    """FR-1108 + ADR-D11-5: existing packs without source_url remain valid."""

    def test_existing_garage_pack_lists_as_local(self) -> None:
        """packs/ in workspace root (no source_url) should list as 'local'."""
        workspace = Path(__file__).resolve().parents[3]
        listed = list_installed_packs(workspace)
        # All 5 existing packs (code-audit/coding/garage/search/writing) listed
        pack_ids = sorted(p["pack_id"] for p in listed)
        assert pack_ids == ["code-audit", "coding", "garage", "search", "writing"]
        # All have source_url == "local" (no source_url field in pack.json)
        for p in listed:
            assert p["source_url"] == "local", (
                f"{p['pack_id']} source_url = {p['source_url']!r}, expected 'local' "
                "(F007 既有 packs without source_url field, FR-1108 backward compat)"
            )
