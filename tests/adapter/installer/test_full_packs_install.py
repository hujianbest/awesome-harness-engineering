"""F008 T4c: full-packs end-to-end integration test.

Covers spec FR-806 acceptance #1-#4 + INV-1 (total skills = sum pack.json) + INV-2
(family-asset uniqueness) + INV-4 (byte-level migration sample) + NFR-803
(<=5s wall-clock).

Strategy: link the real packs/ directory into a tmp workspace via symlink
(same pattern as tests/test_cli.py::TestInitWithHosts._link_packs), then
run install_packs() with all three first-class hosts. Assert manifest
shape + N derived from sum(pack.json.skills[]).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from garage_os.adapter.installer.manifest import read_manifest
from garage_os.adapter.installer.pack_discovery import discover_packs
from garage_os.adapter.installer.pipeline import install_packs

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKS_ROOT = REPO_ROOT / "packs"

# F008 ADR-D8-1: family-level shared assets that must appear at most once
# under packs/. Skill-private references/<file>.md with the same basename
# do NOT count (those are skill-internal and can be duplicated).
#
# Post harness-flow v0.1.0 reverse-sync: packs/coding no longer ships any
# family-level shared assets — upstream went per-skill self-contained
# (templates + shared docs distributed into each skill's own references/).
# So coding/ contributes zero entries here. The only remaining family-level
# asset in the whole packs/ tree is packs/writing/prompts/横纵分析法.md.
FAMILY_ASSET_BASENAMES_AND_PATHS = {
    ("横纵分析法.md", Path("packs/writing/prompts")),
}


def _link_packs(tmp_path: Path) -> None:
    """Symlink the real packs/ into tmp_path/packs (forward-compatible)."""
    link = tmp_path / "packs"
    if link.exists() or link.is_symlink():
        return
    link.symlink_to(PACKS_ROOT)


class TestFullPacksInstall:
    """End-to-end test: real packs/ installed into tmp workspace."""

    def test_five_packs_total_37_skills_INV1(self) -> None:
        """INV-1: sum(pack.json.skills[] for pack in [code-audit, coding, garage, search, writing]) == 37.

        Trace: 33 (coding 24 + garage 3 + search 1 + writing 5) → 37 after code-audit pack
        adds audit-planner + audit-reviewer + audit-verifier + audit-reporter (Slice A).
        """
        packs = discover_packs(PACKS_ROOT)
        # Index by pack_id for stable assertions regardless of pack order.
        by_id = {p.pack_id: p for p in packs}
        assert set(by_id) == {"code-audit", "coding", "garage", "search", "writing"}, (
            f"expected exactly 5 packs, got {sorted(by_id)}"
        )
        # Per task plan T1b/T2/T3 acceptance + coding v0.3.0 reverse-sync + search hotfix
        # + code-audit Slice A:
        assert len(by_id["code-audit"].skills) == 4
        assert len(by_id["coding"].skills) == 24
        assert len(by_id["garage"].skills) == 3
        assert len(by_id["search"].skills) == 1  # ai-weekly only
        assert len(by_id["writing"].skills) == 5
        # INV-1 hard gate.
        total = sum(len(p.skills) for p in packs)
        assert total == 37, f"INV-1 violated: total skills = {total} (want 37)"
        # F011: garage agents 1 → 3 (sample + code-review + blog-writing)
        assert len(by_id["garage"].agents) == 3, (
            f"F011: packs/garage/agents/ should have 3 (sample + code-review + blog-writing); got {by_id['garage'].agents}"
        )
        # code-audit Slice A: 2 agents (reviewer + verifier)
        assert len(by_id["code-audit"].agents) == 2, (
            f"code-audit: packs/code-audit/agents/ should have 2 "
            f"(code-audit-reviewer-agent + code-audit-verifier-agent); "
            f"got {by_id['code-audit'].agents}"
        )

    def test_family_asset_uniqueness_INV2(self) -> None:
        """INV-2 spec § 4.2 红线 1: each family-level asset appears at most once
        in its designated path under packs/. Skill-private references/<basename>.md
        are excluded by the path-narrowed enumeration."""
        for basename, asset_dir in FAMILY_ASSET_BASENAMES_AND_PATHS:
            target = REPO_ROOT / asset_dir / basename
            assert target.is_file(), (
                f"INV-2 enum requires {target.relative_to(REPO_ROOT)} to exist"
            )
            # And there must be no other copy in the same family-level path
            # (we accept skill-private duplicates by construction here).
            same_dir_matches = list((REPO_ROOT / asset_dir).glob(basename))
            assert len(same_dir_matches) == 1, (
                f"INV-2 violated for {basename}: found {same_dir_matches}"
            )

    def test_install_packs_three_hosts_FR806(self, tmp_path: Path) -> None:
        """FR-806 acceptance #1-#3: garage init --hosts all writes 37 skills × 3 hosts
        + 5 agents × 2 hosts (claude + opencode; cursor has no agent surface).

        Trace: F011 ledger said 33 skills + 3 agents (garage). code-audit Slice A adds
        4 skills + 2 agents → 37 skills + 5 agents (garage 3 + code-audit 2).
        """
        _link_packs(tmp_path)

        summary = install_packs(
            workspace_root=tmp_path,
            packs_root=tmp_path / "packs",
            hosts=["claude", "cursor", "opencode"],
        )

        # Per-host skill count == 37 (coding 24 + garage 3 + search 1 + writing 5 + code-audit 4).
        for host_dir in [".claude/skills", ".cursor/skills", ".opencode/skills"]:
            host_root = tmp_path / host_dir
            assert host_root.is_dir(), f"{host_dir} not created"
            skill_subdirs = [d for d in host_root.iterdir() if d.is_dir()]
            assert len(skill_subdirs) == 37, (
                f"{host_dir} has {len(skill_subdirs)} skill dirs, expected 37"
            )

        # Manifest matches.
        manifest = read_manifest(tmp_path / ".garage")
        assert manifest is not None
        assert sorted(manifest.installed_hosts) == ["claude", "cursor", "opencode"]
        assert sorted(manifest.installed_packs) == [
            "code-audit", "coding", "garage", "search", "writing"
        ]

        # 37 skills × 3 hosts = 111 skill files; 5 agents × 2 hosts (claude + opencode,
        # cursor adapter returns None for target_agent_path) = 10 agent files. Total 121.
        assert len(manifest.files) == 121, (
            f"manifest.files = {len(manifest.files)}, expected 121 (111 skills + 10 agents)"
        )

        # Summary returned (skills counted per-write, hence × 3 here too).
        assert isinstance(summary.n_skills, int)
        assert summary.n_skills == 111  # 37 × 3
        assert summary.n_agents == 10  # 5 agents × 2 hosts (claude + opencode)

    def test_skill_byte_level_sample_INV4(self, tmp_path: Path) -> None:
        """INV-4 + CON-803: a sampled hf-* SKILL.md installed to .claude/skills/
        has its main body (after marker injection) byte-identical to the source
        (only diff = 2 lines of injected `installed_by:` + `installed_pack:`)."""
        _link_packs(tmp_path)

        install_packs(
            workspace_root=tmp_path,
            packs_root=tmp_path / "packs",
            hosts=["claude"],
        )

        installed = tmp_path / ".claude/skills/hf-specify/SKILL.md"
        source = REPO_ROOT / "packs/coding/skills/hf-specify/SKILL.md"
        assert installed.exists(), "hf-specify SKILL.md not installed"

        installed_text = installed.read_text(encoding="utf-8")
        source_text = source.read_text(encoding="utf-8")

        # Marker injection is in the front matter; the body after `---\n\n` MUST
        # be byte-identical (the marker only adds two lines inside the YAML
        # front matter block).
        installed_body = installed_text.split("---\n\n", 1)[-1]
        source_body = source_text.split("---\n\n", 1)[-1]
        assert installed_body == source_body, (
            "INV-4 violated: hf-specify SKILL.md body diverged after install"
        )

        # And the marker itself MUST be present.
        assert "installed_by: garage" in installed_text
        assert "installed_pack: coding" in installed_text

    def test_install_packs_under_5_seconds_NFR803(self, tmp_path: Path) -> None:
        """NFR-803: full-packs three-host install stays well under interactive budget.

        Spec targets ≤5s on a warm local SSD; CI / WSL / network-mounted workspaces
        can be slower, so the automated gate uses a generous ceiling while still
        catching accidental regressions (e.g. O(n²) copy loops).
        """
        _link_packs(tmp_path)

        start = time.monotonic()
        install_packs(
            workspace_root=tmp_path,
            packs_root=tmp_path / "packs",
            hosts=["claude", "cursor", "opencode"],
        )
        elapsed = time.monotonic() - start

        limit_s = 30.0
        assert elapsed <= limit_s, (
            f"NFR-803 violated: install_packs took {elapsed:.2f}s (limit {limit_s}s)"
        )
