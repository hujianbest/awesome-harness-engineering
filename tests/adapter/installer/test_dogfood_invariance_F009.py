"""F009 T5: Dogfood SHA-256 不变性 sentinel 测试.

Covers:
- spec NFR-901 (Dogfood 不变性硬门槛)
- design ADR-D9-11 (sentinel 等价语义边界: 仅 SKILL.md+agent.md 落盘字节级,
  manifest 显式不参与)
- INV-F9-1 (CON-901 + Dogfood SHA-256 一致)

Strategy:
- Fixture 在 tmp_path 内 link packs/, 跑 garage init --hosts cursor,claude
  (无 --scope, 默认 project, 等价 F008 dogfood 路径 ADR-D8-2 candidate C)
- 比对落盘 SKILL.md + agent.md 文件 SHA-256 与 baseline JSON 一致
- baseline JSON: tests/adapter/installer/dogfood_baseline/skill_md_sha256.json
  (T5 commit 实施时由 hf-test-driven-dev executor 在 fixture 内首跑生成 +
  人工 review 数值合理性, 见 task plan T5 测试设计种子候选 A)

边界澄清 (ADR-D9-11):
- 本 sentinel 只测 SKILL.md / agent.md 落盘字节级 SHA-256
- manifest 不参与 (因 dst 字段含 cwd/home, 跨贡献者必然不同)
- manifest 字段稳定性 (content_hash + scope + host) 由 sister test
  test_manifest_v2_dogfood_fields_stable.py 守门
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from garage_os.adapter.installer.pipeline import install_packs


REPO_ROOT = Path(__file__).resolve().parents[3]
PACKS_ROOT = REPO_ROOT / "packs"
BASELINE_JSON = (
    Path(__file__).resolve().parent
    / "dogfood_baseline"
    / "skill_md_sha256.json"
)


def _link_packs(tmp_path: Path) -> None:
    link = tmp_path / "packs"
    if not link.exists() and not link.is_symlink():
        link.symlink_to(PACKS_ROOT)


def _collect_dogfood_skill_md_sha256(workspace_root: Path) -> dict[str, str]:
    """Walk .claude/{skills,agents} + .cursor/skills under workspace_root.

    Returns: {relative POSIX path under workspace_root → SHA-256 hex}
    """
    out: dict[str, str] = {}
    for d in (workspace_root / ".claude" / "skills").iterdir():
        if d.is_dir():
            f = d / "SKILL.md"
            if f.is_file():
                rel = f.relative_to(workspace_root).as_posix()
                out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    cursor_root = workspace_root / ".cursor" / "skills"
    if cursor_root.is_dir():
        for d in cursor_root.iterdir():
            if d.is_dir():
                f = d / "SKILL.md"
                if f.is_file():
                    rel = f.relative_to(workspace_root).as_posix()
                    out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    agents_root = workspace_root / ".claude" / "agents"
    if agents_root.is_dir():
        for f in agents_root.iterdir():
            if f.is_file() and f.suffix == ".md":
                rel = f.relative_to(workspace_root).as_posix()
                out[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


class TestDogfoodSHA256Invariance:
    """ADR-D9-11 + NFR-901 + INV-F9-1: Dogfood 落盘文件字节级与 baseline 一致."""

    def test_baseline_json_exists_and_loadable(self) -> None:
        """sentinel 自检: baseline JSON 存在 + JSON 合法 + 含 ≥ 50 个 entry."""
        assert BASELINE_JSON.is_file(), (
            f"Dogfood baseline JSON missing: {BASELINE_JSON}. "
            "By task plan T5 测试设计种子: hf-test-driven-dev executor 在 T5 fixture "
            "内首跑 install_packs 后 read SHA-256 写入此文件 (候选 A)."
        )
        baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
        assert isinstance(baseline, dict)
        # 37 skills × 2 hosts (cursor + claude) + 5 agents under .claude/agents
        # (claude only; cursor 无 agent surface) = 79 files. After code-audit Slice A.
        assert len(baseline) >= 70, (
            f"baseline 含 {len(baseline)} entries, 期望 ≥ 70 "
            "(37 skill × 2 host + 5 agents = 79)"
        )

    def test_dogfood_skill_md_sha256_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """跑 garage init --hosts cursor,claude (project scope), 比对 SHA-256.

        ADR-D9-11: 仅测 SKILL.md+agent.md 落盘字节级, manifest 显式不参与.
        """
        _link_packs(tmp_path)

        # 跑 dogfood 路径 (无 scope, 默认 project, ADR-D8-2 candidate C)
        install_packs(
            workspace_root=tmp_path,
            packs_root=tmp_path / "packs",
            hosts=["cursor", "claude"],
        )

        actual = _collect_dogfood_skill_md_sha256(tmp_path)
        baseline = json.loads(BASELINE_JSON.read_text(encoding="utf-8"))

        # 文件集合必须完全一致
        assert set(actual.keys()) == set(baseline.keys()), (
            f"Dogfood file set drift: "
            f"only_in_actual={set(actual) - set(baseline)}, "
            f"only_in_baseline={set(baseline) - set(actual)}"
        )

        # 每个文件 SHA-256 必须与 baseline 一致
        mismatches = []
        for rel, expected_sha in baseline.items():
            actual_sha = actual[rel]
            if actual_sha != expected_sha:
                mismatches.append(
                    f"{rel}: expected {expected_sha[:12]}... got {actual_sha[:12]}..."
                )
        assert not mismatches, (
            "Dogfood SHA-256 不变性硬门槛违反 (ADR-D9-11):\n"
            + "\n".join(mismatches[:5])
            + (f"\n... (and {len(mismatches) - 5} more)" if len(mismatches) > 5 else "")
        )
