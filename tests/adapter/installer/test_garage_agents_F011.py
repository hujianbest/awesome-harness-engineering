"""F011 T3: 2 production agents (code-review-agent + blog-writing-agent) tests.

Covers FR-1104/1105 + INV-F11-3 + INV-F11-4.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from garage_os.adapter.installer.pack_discovery import discover_packs
from garage_os.adapter.installer.pipeline import install_packs

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKS_ROOT = REPO_ROOT / "packs"


class TestProductionAgentFiles:
    """FR-1104/1105: 2 agent.md 物理存在 + 含 front matter."""

    def test_code_review_agent_file_exists(self) -> None:
        agent_path = PACKS_ROOT / "garage" / "agents" / "code-review-agent.md"
        assert agent_path.is_file()

    def test_blog_writing_agent_file_exists(self) -> None:
        agent_path = PACKS_ROOT / "garage" / "agents" / "blog-writing-agent.md"
        assert agent_path.is_file()

    def test_code_review_agent_has_front_matter(self) -> None:
        content = (PACKS_ROOT / "garage" / "agents" / "code-review-agent.md").read_text(encoding="utf-8")
        # YAML front matter at top
        assert content.startswith("---\n")
        # name + description fields
        assert re.search(r"^name:\s*code-review-agent", content, re.MULTILINE)
        assert re.search(r"^description:", content, re.MULTILINE)

    def test_blog_writing_agent_has_front_matter(self) -> None:
        content = (PACKS_ROOT / "garage" / "agents" / "blog-writing-agent.md").read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert re.search(r"^name:\s*blog-writing-agent", content, re.MULTILINE)
        assert re.search(r"^description:", content, re.MULTILINE)


class TestPackDiscoveryFindsAgents:
    """INV-F11-3: discover_packs lists 3 agents under garage."""

    def test_garage_has_3_agents(self) -> None:
        packs = discover_packs(PACKS_ROOT)
        garage = next((p for p in packs if p.pack_id == "garage"), None)
        assert garage is not None
        assert sorted(garage.agents) == [
            "blog-writing-agent",
            "code-review-agent",
            "garage-sample-agent",
        ]


class TestInstallProductionAgents:
    """INV-F11-3: F007 install pipeline installs all 3 agents to claude + opencode."""

    def test_install_to_claude_includes_3_agents(self, tmp_path: Path) -> None:
        # Symlink real packs/
        (tmp_path / "packs").symlink_to(PACKS_ROOT)
        install_packs(
            workspace_root=tmp_path,
            packs_root=tmp_path / "packs",
            hosts=["claude"],
        )
        agents_dir = tmp_path / ".claude" / "agents"
        assert agents_dir.is_dir()
        agent_files = sorted(p.name for p in agents_dir.glob("*.md"))
        # F011 garage agents (3) + code-audit Slice A agents (2) = 5 total.
        assert agent_files == [
            "blog-writing-agent.md",
            "code-audit-reviewer-agent.md",
            "code-audit-verifier-agent.md",
            "code-review-agent.md",
            "garage-sample-agent.md",
        ]

    def test_install_to_opencode_includes_3_agents(self, tmp_path: Path) -> None:
        (tmp_path / "packs").symlink_to(PACKS_ROOT)
        install_packs(
            workspace_root=tmp_path,
            packs_root=tmp_path / "packs",
            hosts=["opencode"],
        )
        agents_dir = tmp_path / ".opencode" / "agent"
        assert agents_dir.is_dir()
        agent_files = sorted(p.name for p in agents_dir.glob("*.md"))
        # F011 garage agents (3) + code-audit Slice A agents (2) = 5 total.
        assert agent_files == [
            "blog-writing-agent.md",
            "code-audit-reviewer-agent.md",
            "code-audit-verifier-agent.md",
            "code-review-agent.md",
            "garage-sample-agent.md",
        ]

    def test_cursor_no_agent_surface(self, tmp_path: Path) -> None:
        """Cursor 不装 agent (与 F007 既有行为一致)."""
        (tmp_path / "packs").symlink_to(PACKS_ROOT)
        install_packs(
            workspace_root=tmp_path,
            packs_root=tmp_path / "packs",
            hosts=["cursor"],
        )
        # No .cursor/agents/ created
        assert not (tmp_path / ".cursor" / "agents").exists()
        assert not (tmp_path / ".cursor" / "agent").exists()
