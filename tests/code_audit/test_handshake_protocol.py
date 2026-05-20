"""Sentinel tests for the v0.2.1 handshake-enforcement contract.

These are repo-state sentinel tests — they assert that critical
"STOP and wait for user" phrasing is present in the right places. If
someone trims down the description / Hard Gate / Step 0.5 wording
without realising it's load-bearing, this test catches the drift
before LLMs start skipping the handshake again.

History:
    v0.2.0 added the project-profile + review_checklist handshake to
    audit-planner Step 0.5. In practice, LLMs frequently printed the
    checklist then continued to slice modules + scan in the same turn
    without waiting for user confirmation. v0.2.1 strengthens the
    contract via (1) a top-of-file ⛔ CRITICAL callout in agent.md and
    planner SKILL.md, (2) a new handshake-protocol.md reference doc,
    (3) audit-reviewer Handshake Re-Gate as a second gate.

What this test does NOT do:
    It does NOT verify runtime LLM behaviour — that's not feasible in
    a unit test. It verifies the docs that the LLM reads. The actual
    runtime correctness has to be validated manually by end users; if
    the LLM still skips the handshake despite this wording, the fix is
    to strengthen the wording further, not to delete this test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "packs" / "code-audit"

PLANNER_SKILL_MD = PACK_ROOT / "skills" / "audit-planner" / "SKILL.md"
REVIEWER_AGENT_MD = PACK_ROOT / "agents" / "code-audit-reviewer-agent.md"
REVIEWER_SKILL_MD = PACK_ROOT / "skills" / "audit-reviewer" / "SKILL.md"
HANDSHAKE_PROTOCOL_MD = (
    PACK_ROOT
    / "skills"
    / "audit-planner"
    / "references"
    / "handshake-protocol.md"
)
PACK_JSON = PACK_ROOT / "pack.json"


def _read(path: Path) -> str:
    assert path.is_file(), f"Required file missing: {path}"
    return path.read_text(encoding="utf-8")


class TestPackVersion:
    """v0.2.1 published in pack metadata."""

    def test_pack_json_version_is_0_2_1(self) -> None:
        text = _read(PACK_JSON)
        assert '"version": "0.2.1"' in text, (
            "pack.json version must be 0.2.1 to reflect the handshake-enforcement fix. "
            "If you're bumping past 0.2.1, also update this assertion intentionally."
        )

    def test_pack_json_description_mentions_handshake_protocol(self) -> None:
        text = _read(PACK_JSON)
        # The description is the host's first hint about the agent's behaviour
        # — it must mention the handshake.
        assert "handshake" in text.lower(), (
            "pack.json description must call out the handshake protocol "
            "so hosts know this is a STOP-and-wait pack."
        )


class TestHandshakeProtocolReference:
    """The new handshake-protocol.md reference must exist + cover the essentials."""

    def test_handshake_protocol_file_present(self) -> None:
        assert HANDSHAKE_PROTOCOL_MD.is_file(), (
            f"handshake-protocol.md missing: {HANDSHAKE_PROTOCOL_MD}. "
            "This is the canonical anti-pattern doc that v0.2.1 references "
            "from both audit-planner SKILL.md and code-audit-reviewer-agent.md."
        )

    @pytest.mark.parametrize(
        "phrase",
        [
            "握手最小单元",  # Section 2: two-message round-trip
            "=== ⏸️ 等待确认 ===",  # The visual STOP marker
            "GOOD",  # GOOD vs BAD examples (section 4)
            "BAD",
            "self-check",  # Section 6: agent self-check
            "Bypass",  # Section 5: explicit bypass clauses
            "skip handshake",  # Bypass keyword
            "--yes",  # Bypass keyword
            "restart-planner",  # Re-Gate command (cross-link)
            "兜底",  # Section 7: reviewer Re-Gate backstop
        ],
    )
    def test_handshake_protocol_covers_essential_concept(self, phrase: str) -> None:
        text = _read(HANDSHAKE_PROTOCOL_MD)
        assert phrase in text, (
            f"handshake-protocol.md missing essential phrase {phrase!r}. "
            "This phrase is load-bearing for the v0.2.1 handshake contract."
        )

    def test_handshake_protocol_contains_at_least_one_good_example(self) -> None:
        text = _read(HANDSHAKE_PROTOCOL_MD)
        # Need at least one "✅ GOOD" header to anchor the agent on correct behaviour.
        assert "✅ GOOD" in text, (
            "handshake-protocol.md must show at least one ✅ GOOD example "
            "of a correct stop-and-wait handshake."
        )

    def test_handshake_protocol_contains_at_least_three_bad_examples(self) -> None:
        text = _read(HANDSHAKE_PROTOCOL_MD)
        # Want multiple anti-patterns spelled out so the LLM has more to pattern-match against.
        bad_count = text.count("❌ BAD")
        assert bad_count >= 3, (
            f"handshake-protocol.md should list at least 3 ❌ BAD anti-patterns "
            f"(found {bad_count}). The whole point of the doc is to give the "
            "LLM a rich catalogue of mistakes to avoid."
        )


class TestPlannerSkillEnforcement:
    """audit-planner SKILL.md must front-load the handshake contract."""

    def test_description_field_calls_out_stop_and_wait(self) -> None:
        # Frontmatter description is what the host reads first to classify the
        # skill. The 'MUST stop and wait' phrasing has to be in there.
        text = _read(PLANNER_SKILL_MD)
        head = text[:2500]  # description lives in the YAML frontmatter at the top
        # Look for "MUST stop and wait" or similar imperative in the description.
        # We accept either uppercase MUST or 必须 (Chinese) + stop/wait/确认 verbs.
        assert "MUST stop and wait" in head or "必须停下" in head, (
            "audit-planner SKILL.md description must imperatively state "
            "the skill stops and waits for explicit user confirmation. "
            "Soft language ('confirms with user') is not enough."
        )

    def test_critical_callout_appears_before_workflow(self) -> None:
        text = _read(PLANNER_SKILL_MD)
        critical_idx = text.find("⛔ CRITICAL")
        workflow_idx = text.find("## Workflow")
        assert critical_idx > 0, "audit-planner SKILL.md missing ⛔ CRITICAL callout"
        assert workflow_idx > 0, "audit-planner SKILL.md missing ## Workflow section"
        assert critical_idx < workflow_idx, (
            "⛔ CRITICAL callout must appear BEFORE the ## Workflow section "
            "so the LLM reads the STOP contract before the step-by-step recipe."
        )

    @pytest.mark.parametrize(
        "phrase",
        [
            "⛔ CRITICAL",
            "握手没完成",
            "禁止",  # explicit prohibition
            "skip handshake",
            "--yes",
            "STOP",
            "handshake-protocol.md",  # cross-link to the new reference
        ],
    )
    def test_planner_skill_contains_phrase(self, phrase: str) -> None:
        text = _read(PLANNER_SKILL_MD)
        assert phrase in text, (
            f"audit-planner SKILL.md missing essential phrase {phrase!r}. "
            "The phrase is load-bearing for v0.2.1 handshake enforcement."
        )

    def test_planner_step_0_5_contains_strict_stop_marker(self) -> None:
        text = _read(PLANNER_SKILL_MD)
        # Step 0.5 must contain the literal "等待确认" emoji marker that we
        # also reference from handshake-protocol.md as the visual STOP signal.
        assert "=== ⏸️ 等待确认 ===" in text, (
            "audit-planner SKILL.md Step 0.5 must contain the literal "
            "`=== ⏸️ 等待确认 ===` marker as the visual STOP signal."
        )

    def test_planner_skill_removes_v0_2_0_loophole(self) -> None:
        text = _read(PLANNER_SKILL_MD)
        # The v0.2.0 doc said "非交互场景（--yes / agent 自动模式）：跳过确认"
        # — that "agent 自动模式" clause is the loophole that let LLMs decide
        # for themselves to skip. v0.2.1 removes this; only user-provided
        # bypass keywords count.
        assert "agent 自动模式" not in text, (
            "audit-planner SKILL.md must NOT contain the v0.2.0 loophole "
            "'agent 自动模式：跳过确认' — that wording lets the LLM decide "
            "to skip handshake on its own. Only user-typed bypass keywords "
            "in the original request count (see Step 0.5.e)."
        )


class TestAgentEnforcement:
    """code-audit-reviewer-agent.md must front-load the handshake contract."""

    def test_description_starts_with_critical_warning(self) -> None:
        text = _read(REVIEWER_AGENT_MD)
        head = text[:3000]
        assert "CRITICAL" in head, (
            "code-audit-reviewer-agent.md description must include the word "
            "'CRITICAL' to flag the must-stop-and-wait contract to the host."
        )
        # Description should explicitly forbid the "I'm running as an agent" excuse.
        assert "NEVER skip the handshake" in head or "never skip" in head.lower(), (
            "agent description must explicitly say the handshake MUST NOT be "
            "skipped just because the LLM is running 'as an agent'."
        )

    def test_critical_callout_appears_before_workflow(self) -> None:
        text = _read(REVIEWER_AGENT_MD)
        critical_idx = text.find("⛔ CRITICAL")
        workflow_idx = text.find("## Workflow")
        assert critical_idx > 0, "agent.md missing ⛔ CRITICAL callout"
        assert workflow_idx > 0, "agent.md missing ## Workflow section"
        assert critical_idx < workflow_idx, (
            "⛔ CRITICAL callout must appear BEFORE the ## Workflow section."
        )

    @pytest.mark.parametrize(
        "phrase",
        [
            "⛔ CRITICAL",
            "两次",  # at-least-two-message-roundtrip contract
            "禁止做的事",  # what's forbidden during the handshake
            "skip handshake",
            "--yes",
            "STOP",
            "Common Mistakes",  # the new section enumerating real anti-patterns
            "agent 自己不算同意者",
            "handshake-protocol.md",  # cross-link
        ],
    )
    def test_agent_md_contains_phrase(self, phrase: str) -> None:
        text = _read(REVIEWER_AGENT_MD)
        assert phrase in text, (
            f"code-audit-reviewer-agent.md missing essential phrase {phrase!r}."
        )

    def test_agent_workflow_keeps_handshake_as_blocking_step(self) -> None:
        text = _read(REVIEWER_AGENT_MD)
        # Step 3 is the handshake step in v0.2.1 (was Step 2.5 in v0.2.0).
        # The marker '🛑 HANDSHAKE' must appear so it visually stands out
        # in the step header.
        assert "🛑 HANDSHAKE" in text, (
            "agent.md Workflow must contain a step header with '🛑 HANDSHAKE' "
            "so the LLM cannot miss it."
        )


class TestReviewerReGate:
    """audit-reviewer SKILL.md must contain the second-gate Handshake Re-Gate."""

    def test_description_mentions_halt_on_unconfirmed(self) -> None:
        text = _read(REVIEWER_SKILL_MD)
        head = text[:3000]
        assert "halt" in head.lower() or "Halt" in head or "HALT" in head, (
            "audit-reviewer SKILL.md description must mention that reviewer "
            "halts (not just warns) when review_checklist is not user-confirmed."
        )
        assert "user_confirmed" in head, (
            "audit-reviewer SKILL.md description must reference review_checklist.user_confirmed."
        )

    @pytest.mark.parametrize(
        "phrase",
        [
            "Handshake Re-Gate",  # name of the new section
            "二次闸门",  # Chinese phrasing
            "user_confirmed",
            "restart-planner",
            "skip-and-warn",
            "=== ⏸️ 等待确认 ===",  # reuse same visual STOP marker
            "Re-Gate vs Planner Handshake",  # comparison subsection
        ],
    )
    def test_reviewer_skill_contains_phrase(self, phrase: str) -> None:
        text = _read(REVIEWER_SKILL_MD)
        assert phrase in text, (
            f"audit-reviewer SKILL.md missing essential phrase {phrase!r}."
        )

    def test_reviewer_skill_re_gate_lists_all_user_commands(self) -> None:
        text = _read(REVIEWER_SKILL_MD)
        # All 6 user-reply commands the Re-Gate accepts must be enumerated
        # so users (and the LLM rendering the prompt) know the full menu.
        for cmd in ("confirm", "del", "add", "edit", "restart-planner", "skip-and-warn"):
            assert cmd in text, (
                f"audit-reviewer Re-Gate must enumerate user command '{cmd}'."
            )

    def test_workflow_step1_triggers_re_gate_before_status_change(self) -> None:
        text = _read(REVIEWER_SKILL_MD)
        # Step 1 must explicitly call out the Re-Gate check + that it happens
        # BEFORE module status is changed to in-review (so we don't half-mutate
        # state on a halted run).
        # We look for both "Handshake Re-Gate" and "in-review" within Workflow.
        wf_start = text.find("## Workflow")
        assert wf_start > 0, "audit-reviewer SKILL.md missing ## Workflow"
        wf = text[wf_start:]
        assert "Handshake Re-Gate" in wf, (
            "Workflow Step 1 must reference the Handshake Re-Gate so the LLM "
            "knows to run the gate before any source-file reads."
        )
        # The Re-Gate check should appear before the in-review transition,
        # i.e. earlier in the workflow text.
        re_gate_idx = wf.find("Re-Gate")
        in_review_idx = wf.find("in-review")
        assert re_gate_idx > 0 and in_review_idx > 0
        assert re_gate_idx < in_review_idx, (
            "Re-Gate check must appear before the 'status → in-review' transition "
            "so a halted run doesn't half-mutate plan.json."
        )


class TestREADMEDocumentsTheFix:
    """README must surface the v0.2.1 fix so downstream users understand it."""

    def test_readme_has_v0_2_1_release_note(self) -> None:
        text = _read(PACK_ROOT / "README.md")
        assert "v0.2.1" in text, (
            "packs/code-audit/README.md must document the v0.2.1 release."
        )
        assert "握手" in text or "handshake" in text.lower(), (
            "v0.2.1 README section must call out the handshake-enforcement fix."
        )

    def test_readme_documents_re_gate(self) -> None:
        text = _read(PACK_ROOT / "README.md")
        assert "Re-Gate" in text or "二次闸门" in text, (
            "README must explain the audit-reviewer Handshake Re-Gate as the "
            "second-gate backstop introduced in v0.2.1."
        )
