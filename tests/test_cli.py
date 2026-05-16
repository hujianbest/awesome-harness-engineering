"""Tests for garage-agent CLI."""

import json
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

import pytest

from garage_os.cli import main
from garage_os.storage.file_storage import FileStorage


class TestInitCreatesStructure:
    """Test that 'garage init' creates the expected directory structure."""

    EXPECTED_SUBDIRS = [
        "config/tools",
        "contracts",
        "knowledge/.metadata",
        "knowledge/decisions",
        "knowledge/patterns",
        "knowledge/solutions",
        "experience/records",
        "sessions/active",
        "sessions/archived",
    ]

    def test_init_creates_structure(self, tmp_path: Path) -> None:
        """init should create all expected sub-directories under .garage/."""
        main(["init", "--path", str(tmp_path)])

        garage_dir = tmp_path / ".garage"
        assert garage_dir.is_dir()

        for subdir in self.EXPECTED_SUBDIRS:
            assert (garage_dir / subdir).is_dir(), f"Missing .garage/{subdir}"

        # README should also exist
        assert (garage_dir / "README.md").is_file()


class TestInitIdempotent:
    """Test that running init twice does not raise."""

    def test_init_idempotent(self, tmp_path: Path) -> None:
        """Running init twice should succeed without errors."""
        main(["init", "--path", str(tmp_path)])
        # Second init should not raise
        main(["init", "--path", str(tmp_path)])

        garage_dir = tmp_path / ".garage"
        assert garage_dir.is_dir()


class TestStatusShowsStats:
    """Test that 'garage status' displays statistics when data exists."""

    def test_status_shows_stats(self, tmp_path: Path, capsys) -> None:
        """status should show session count, knowledge count, and recent experience."""
        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Create active and archived sessions using the runtime layout
        active_session_dir = garage_dir / "sessions" / "active" / "session-001"
        active_session_dir.mkdir(parents=True)
        (active_session_dir / "session.json").write_text(
            json.dumps({"session_id": "session-001"}), encoding="utf-8"
        )
        archived_session_dir = garage_dir / "sessions" / "archived" / "session-002"
        archived_session_dir.mkdir(parents=True)
        (archived_session_dir / "session.json").write_text(
            json.dumps({"session_id": "session-002"}), encoding="utf-8"
        )

        # Create a knowledge entry
        knowledge_decisions = garage_dir / "knowledge" / "decisions"
        (knowledge_decisions / "decision-001.md").write_text(
            "---\ntitle: test\n---\nbody", encoding="utf-8"
        )

        # Create an experience record
        experience_records = garage_dir / "experience" / "records"
        (experience_records / "exp-001.json").write_text(
            json.dumps({"id": "exp-001", "timestamp": "2025-01-15T10:00:00"}),
            encoding="utf-8",
        )

        main(["status", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert "Sessions: 2" in captured.out
        assert "active: 1" in captured.out
        assert "archived: 1" in captured.out
        assert "Knowledge entries: 1" in captured.out
        assert "Experience records: 1" in captured.out
        assert "2025-01-15T10:00:00" in captured.out


class TestStatusEmpty:
    """Test that 'garage status' shows 'No data' for empty repos."""

    def test_status_empty(self, tmp_path: Path, capsys) -> None:
        """status on empty .garage/ should print 'No data'."""
        main(["init", "--path", str(tmp_path)])
        main(["status", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert "No data" in captured.out

    def test_status_no_garage_dir(self, tmp_path: Path, capsys) -> None:
        """status without .garage/ should say directory not found."""
        main(["status", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert "No .garage/ directory found" in captured.out


class TestNoArgsShowsHelp:
    """Test that running CLI with no arguments shows help."""

    def test_no_args_shows_help(self, capsys) -> None:
        """Calling main([]) should print help text."""
        # Patch _find_garage_root so we don't depend on the real FS
        with patch("garage_os.cli._find_garage_root", return_value=Path.cwd()):
            main([])

        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "garage" in captured.out.lower()


class TestUnknownCommandShowsHelp:
    """Test that an unknown command shows help."""

    def test_unknown_command_shows_help(self, capsys) -> None:
        """An unrecognized sub-command should cause argparse to error / show help."""
        # argparse will raise SystemExit for unknown commands when using subparsers
        # Since we pass None to command, let's test the fallback behavior
        # argparse handles unknown commands by printing help and exiting with code 2
        import pytest

        with pytest.raises(SystemExit) as exc_info:
            main(["nonexistent"])

        # argparse exits with code 2 for unrecognized arguments
        assert exc_info.value.code == 2


class TestRunCommand:
    """Test that 'garage run' invokes skills and records experience."""

    def test_run_success(self, tmp_path: Path, capsys) -> None:
        """run should invoke skill, archive a completed session, and record experience."""
        from garage_os.types import SessionState

        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Mock ClaudeCodeAdapter.invoke_skill to return success
        mock_result = {"output": "Skill output", "exit_code": 0, "success": True}
        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.return_value = mock_result
            MockAdapter.return_value = mock_adapter

            result = main(["run", "test-skill", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert result == 0
        assert "Skill 'test-skill' completed successfully" in captured.out
        assert "Experience recorded:" in captured.out
        assert "Session archived:" in captured.out

        # Check session moved to archived and was updated to completed
        assert list((garage_dir / "sessions" / "active").iterdir()) == []
        sessions = list((garage_dir / "sessions" / "archived").iterdir())
        assert len(sessions) == 1
        session_file = sessions[0] / "session.json"
        session_data = json.loads(session_file.read_text(encoding="utf-8"))
        assert session_data["state"] == SessionState.COMPLETED.value
        assert session_data["pack_id"] == "test-skill"

        # Check experience record was created
        experience_records = list((garage_dir / "experience" / "records").glob("*.json"))
        assert len(experience_records) == 1
        exp_data = json.loads(experience_records[0].read_text(encoding="utf-8"))
        assert exp_data["outcome"] == "success"
        assert exp_data["skill_ids"] == ["test-skill"]
        assert exp_data["session_id"] == session_data["session_id"]

    def test_run_failure(self, tmp_path: Path, capsys) -> None:
        """run should archive failed sessions and record failed experience."""
        from garage_os.types import SessionState

        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Mock ClaudeCodeAdapter.invoke_skill to return failure
        mock_result = {"output": "Error occurred", "exit_code": 1, "success": False}
        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.return_value = mock_result
            MockAdapter.return_value = mock_adapter

            result = main(["run", "failing-skill", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert result == 1
        assert "Skill 'failing-skill' failed" in captured.out
        assert "Experience recorded:" in captured.out
        assert "Session archived:" in captured.out

        # Check session moved to archived and was updated to failed
        assert list((garage_dir / "sessions" / "active").iterdir()) == []
        sessions = list((garage_dir / "sessions" / "archived").iterdir())
        assert len(sessions) == 1
        session_file = sessions[0] / "session.json"
        session_data = json.loads(session_file.read_text(encoding="utf-8"))
        assert session_data["state"] == SessionState.FAILED.value

        # Check experience record was created with failure outcome
        experience_records = list((garage_dir / "experience" / "records").glob("*.json"))
        assert len(experience_records) == 1
        exp_data = json.loads(experience_records[0].read_text(encoding="utf-8"))
        assert exp_data["outcome"] == "failure"

    def test_run_creates_session(self, tmp_path: Path) -> None:
        """run should create and archive a new session for each invocation."""
        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Mock ClaudeCodeAdapter
        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.return_value = {
                "output": "",
                "exit_code": 0,
                "success": True,
            }
            MockAdapter.return_value = mock_adapter

            # Run two skills
            main(["run", "skill1", "--path", str(tmp_path)])
            main(["run", "skill2", "--path", str(tmp_path)])

        # Check two archived sessions were created
        assert list((garage_dir / "sessions" / "active").iterdir()) == []
        sessions = list((garage_dir / "sessions" / "archived").iterdir())
        assert len(sessions) == 2

    def test_run_returns_nonzero_on_exception(self, tmp_path: Path, capsys) -> None:
        """run should return non-zero when the adapter raises an exception."""
        main(["init", "--path", str(tmp_path)])

        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.side_effect = Exception("boom")
            MockAdapter.return_value = mock_adapter

            result = main(["run", "broken-skill", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert result == 1
        assert "Error running skill 'broken-skill': boom" in captured.out

    def test_run_passes_timeout_to_adapter(self, tmp_path: Path) -> None:
        """run should pass the requested timeout through to ClaudeCodeAdapter."""
        main(["init", "--path", str(tmp_path)])

        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.return_value = {
                "output": "",
                "exit_code": 0,
                "success": True,
            }
            MockAdapter.return_value = mock_adapter

            result = main(
                ["run", "timed-skill", "--timeout", "17", "--path", str(tmp_path)]
            )

        assert result == 0
        MockAdapter.assert_called_once_with(tmp_path, timeout=17)

    def test_run_skips_recommendation_when_disabled(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """run must NOT print recommendations when the feature flag is off (T4 acceptance)."""
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"
        platform_json = garage_dir / "config" / "platform.json"
        config = json.loads(platform_json.read_text(encoding="utf-8"))
        assert config["memory"]["recommendation_enabled"] is False

        decision_path = garage_dir / "knowledge" / "decisions" / "decision-disabled.md"
        decision_path.write_text(
            """---
id: decision-disabled
type: decision
topic: Recommendation for disabled-skill
date: 2026-04-18T10:00:00
tags: [disabled-skill, workspace-first]
status: active
version: 1
---

Should not be surfaced when recommendation is disabled.
""",
            encoding="utf-8",
        )

        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter, \
            patch("garage_os.cli.RecommendationService") as MockRecommendationService:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.return_value = {
                "output": "",
                "exit_code": 0,
                "success": True,
            }
            MockAdapter.return_value = mock_adapter

            result = main(["run", "disabled-skill", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert result == 0
        assert "Recommendations:" not in captured.out
        MockRecommendationService.assert_not_called()

    def test_run_shows_recommendation_summary_when_enabled(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """run should print a recommendation summary before execution when enabled."""
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"
        platform_json = garage_dir / "config" / "platform.json"
        config = json.loads(platform_json.read_text(encoding="utf-8"))
        config["memory"]["recommendation_enabled"] = True
        platform_json.write_text(json.dumps(config), encoding="utf-8")

        decision_path = garage_dir / "knowledge" / "decisions" / "decision-memory.md"
        decision_path.write_text(
            """---
id: decision-memory
type: decision
topic: Recommendation for timed-skill
date: 2026-04-18T10:00:00
tags: [timed-skill, workspace-first]
status: active
version: 1
---

Use workspace-first memory recommendations.
""",
            encoding="utf-8",
        )

        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.return_value = {
                "output": "",
                "exit_code": 0,
                "success": True,
            }
            MockAdapter.return_value = mock_adapter

            result = main(["run", "timed-skill", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert result == 0
        assert "Recommendations:" in captured.out
        assert "Recommendation for timed-skill" in captured.out


class TestExperienceRecording:
    """Test that experience is automatically recorded after skill execution."""

    def test_experience_recorded_on_success(self, tmp_path: Path) -> None:
        """Successful skill execution should create experience record with success outcome."""
        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Mock ClaudeCodeAdapter
        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.return_value = {
                "output": "Success",
                "exit_code": 0,
                "success": True,
            }
            MockAdapter.return_value = mock_adapter

            main(["run", "test-skill", "--path", str(tmp_path)])

        # Check experience record
        experience_records = list((garage_dir / "experience" / "records").glob("*.json"))
        assert len(experience_records) == 1
        exp_data = json.loads(experience_records[0].read_text(encoding="utf-8"))

        # Verify fields
        assert exp_data["outcome"] == "success"
        assert exp_data["task_type"] == "skill_execution"
        assert exp_data["skill_ids"] == ["test-skill"]
        assert exp_data["problem_domain"] == "test-skill"
        assert "duration_seconds" in exp_data
        assert "session_id" in exp_data
        assert "created_at" in exp_data
        assert "updated_at" in exp_data

    def test_experience_recorded_on_failure(self, tmp_path: Path) -> None:
        """Failed skill execution should create experience record with failure outcome."""
        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Mock ClaudeCodeAdapter to raise exception
        with patch("garage_os.cli.ClaudeCodeAdapter") as MockAdapter:
            mock_adapter = MagicMock()
            mock_adapter.invoke_skill.side_effect = Exception("Skill failed")
            MockAdapter.return_value = mock_adapter

            main(["run", "failing-skill", "--path", str(tmp_path)])

        # Check experience record was created even on exception
        experience_records = list((garage_dir / "experience" / "records").glob("*.json"))
        assert len(experience_records) == 1
        exp_data = json.loads(experience_records[0].read_text(encoding="utf-8"))

        # Verify failure outcome
        assert exp_data["outcome"] == "failure"
        assert exp_data["skill_ids"] == ["failing-skill"]


class TestMemoryReviewCommand:
    """Test CLI memory review command."""

    def test_memory_review_shows_batch_summary(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """memory review should show candidate batch summary."""
        from garage_os.memory.candidate_store import CandidateStore

        main(["init", "--path", str(tmp_path)])
        storage = FileStorage(tmp_path / ".garage")
        candidate_store = CandidateStore(storage)
        candidate_store.store_candidate(
            {
                "schema_version": "1",
                "candidate_id": "candidate-001",
                "candidate_type": "decision",
                "session_id": "session-001",
                "source_artifacts": ["docs/designs/example.md"],
                "match_reasons": ["artifact:docs/designs/example.md"],
                "status": "pending_review",
                "priority_score": 0.9,
                "title": "Use candidate batches",
                "summary": "Summary",
                "content": "Body",
            }
        )
        candidate_store.store_batch(
            {
                "batch_id": "batch-001",
                "session_id": "session-001",
                "status": "pending_review",
                "trigger": "session_archived",
                "candidate_ids": ["candidate-001"],
                "truncated_count": 0,
                "evaluation_summary": "evaluated_with_candidates",
                "created_at": "2026-04-18T10:00:00",
                "metadata": {},
            }
        )

        result = main(["memory", "review", "batch-001", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert result == 0
        assert "Candidate Batch: batch-001" in captured.out
        assert "Use candidate batches" in captured.out

    def test_memory_review_batch_reject_updates_candidates(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """batch_reject should reject every candidate in the batch."""
        from garage_os.memory.candidate_store import CandidateStore

        main(["init", "--path", str(tmp_path)])
        storage = FileStorage(tmp_path / ".garage")
        candidate_store = CandidateStore(storage)
        for candidate_id in ["candidate-001", "candidate-002"]:
            candidate_store.store_candidate(
                {
                    "schema_version": "1",
                    "candidate_id": candidate_id,
                    "candidate_type": "decision",
                    "session_id": "session-001",
                    "source_artifacts": ["docs/designs/example.md"],
                    "match_reasons": ["artifact:docs/designs/example.md"],
                    "status": "pending_review",
                    "priority_score": 0.9,
                    "title": f"Title {candidate_id}",
                    "summary": "Summary",
                    "content": "Body",
                }
            )
        candidate_store.store_batch(
            {
                "batch_id": "batch-001",
                "session_id": "session-001",
                "status": "pending_review",
                "trigger": "session_archived",
                "candidate_ids": ["candidate-001", "candidate-002"],
                "truncated_count": 0,
                "evaluation_summary": "evaluated_with_candidates",
                "created_at": "2026-04-18T10:00:00",
                "metadata": {},
            }
        )

        result = main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "batch_reject",
                "--path",
                str(tmp_path),
            ]
        )

        captured = capsys.readouterr()
        assert result == 0
        assert "Applied action 'batch_reject'" in captured.out
        assert candidate_store.retrieve_candidate("candidate-001")["status"] == "rejected"
        assert candidate_store.retrieve_candidate("candidate-002")["status"] == "rejected"

    def test_memory_review_defer_marks_batch_pending_later(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """defer should keep the batch available for later review."""
        from garage_os.memory.candidate_store import CandidateStore

        main(["init", "--path", str(tmp_path)])
        storage = FileStorage(tmp_path / ".garage")
        candidate_store = CandidateStore(storage)
        candidate_store.store_candidate(
            {
                "schema_version": "1",
                "candidate_id": "candidate-001",
                "candidate_type": "decision",
                "session_id": "session-001",
                "source_artifacts": ["docs/designs/example.md"],
                "match_reasons": ["artifact:docs/designs/example.md"],
                "status": "pending_review",
                "priority_score": 0.9,
                "title": "Keep later",
                "summary": "Summary",
                "content": "Body",
            }
        )
        candidate_store.store_batch(
            {
                "batch_id": "batch-001",
                "session_id": "session-001",
                "status": "pending_review",
                "trigger": "session_archived",
                "candidate_ids": ["candidate-001"],
                "truncated_count": 0,
                "evaluation_summary": "evaluated_with_candidates",
                "created_at": "2026-04-18T10:00:00",
                "metadata": {},
            }
        )

        result = main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "defer",
                "--path",
                str(tmp_path),
            ]
        )

        captured = capsys.readouterr()
        assert result == 0
        assert "Applied action 'defer'" in captured.out
        assert candidate_store.retrieve_batch("batch-001")["status"] == "deferred"


    def test_memory_review_accept_requires_strategy_when_conflict_exists(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """accept must surface the FR-304 strategy choice when a similar entry exists."""
        from garage_os.memory.candidate_store import CandidateStore

        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"
        decisions_dir = garage_dir / "knowledge" / "decisions"
        decisions_dir.mkdir(parents=True, exist_ok=True)
        (decisions_dir / "decision-existing.md").write_text(
            """---
id: existing
type: decision
topic: Use candidate batches
date: 2026-04-18T10:00:00
tags: [memory]
status: active
version: 1
---

Existing decision body.
""",
            encoding="utf-8",
        )

        storage = FileStorage(garage_dir)
        candidate_store = CandidateStore(storage)
        candidate_store.store_candidate(
            {
                "schema_version": "1",
                "candidate_id": "candidate-001",
                "candidate_type": "decision",
                "session_id": "session-001",
                "source_artifacts": ["docs/designs/example.md"],
                "source_evidence_anchors": [
                    {"kind": "artifact_excerpt", "ref": "docs/designs/example.md#decision"}
                ],
                "match_reasons": ["artifact:docs/designs/example.md"],
                "status": "pending_review",
                "priority_score": 0.9,
                "title": "Use candidate batches",
                "summary": "Summary",
                "content": "Body",
                "tags": ["memory"],
            }
        )
        candidate_store.store_batch(
            {
                "batch_id": "batch-001",
                "session_id": "session-001",
                "status": "pending_review",
                "trigger": "session_archived",
                "candidate_ids": ["candidate-001"],
                "truncated_count": 0,
                "evaluation_summary": "evaluated_with_candidates",
                "created_at": "2026-04-18T10:00:00",
                "metadata": {},
            }
        )

        result = main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "accept",
                "--candidate-id",
                "candidate-001",
                "--path",
                str(tmp_path),
            ]
        )

        captured = capsys.readouterr()
        assert result == 1
        assert "--strategy" in captured.out

    def test_memory_review_abandon_skips_publication(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """abandon must be a first-class CLI action that skips publication (FR-304)."""
        from garage_os.memory.candidate_store import CandidateStore

        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"
        storage = FileStorage(garage_dir)
        candidate_store = CandidateStore(storage)
        candidate_store.store_candidate(
            {
                "schema_version": "1",
                "candidate_id": "candidate-001",
                "candidate_type": "decision",
                "session_id": "session-001",
                "source_artifacts": ["docs/designs/example.md"],
                "source_evidence_anchors": [
                    {"kind": "artifact_excerpt", "ref": "docs/designs/example.md#decision"}
                ],
                "match_reasons": ["artifact:docs/designs/example.md"],
                "status": "pending_review",
                "priority_score": 0.9,
                "title": "Abandon-able candidate",
                "summary": "Summary",
                "content": "Body",
            }
        )
        candidate_store.store_batch(
            {
                "batch_id": "batch-001",
                "session_id": "session-001",
                "status": "pending_review",
                "trigger": "session_archived",
                "candidate_ids": ["candidate-001"],
                "truncated_count": 0,
                "evaluation_summary": "evaluated_with_candidates",
                "created_at": "2026-04-18T10:00:00",
                "metadata": {},
            }
        )

        result = main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "abandon",
                "--candidate-id",
                "candidate-001",
                "--path",
                str(tmp_path),
            ]
        )

        captured = capsys.readouterr()
        assert result == 0
        assert "abandon" in captured.out.lower()
        assert candidate_store.retrieve_candidate("candidate-001")["status"] == "abandoned"
        published = list((garage_dir / "knowledge" / "decisions").glob("*.md"))
        assert published == []


class TestMemoryReviewAbandonDualPaths:
    """F004 T3: CLI abandon dual-path differentiation (FR-403a + FR-403b + ADR-403).

    Locks differentiation between:
    - ``--action=abandon``                       -> intentionally drop candidate
    - ``--action=accept --strategy=abandon``     -> abandon because of conflict
    """

    def _seed_candidate(
        self,
        tmp_path: Path,
        candidate_id: str = "candidate-001",
        title: str = "Dual-path abandon candidate",
        tags: Optional[list[str]] = None,
    ):
        from garage_os.memory.candidate_store import CandidateStore

        garage_dir = tmp_path / ".garage"
        storage = FileStorage(garage_dir)
        candidate_store = CandidateStore(storage)
        candidate_store.store_candidate(
            {
                "schema_version": "1",
                "candidate_id": candidate_id,
                "candidate_type": "decision",
                "session_id": "session-001",
                "source_artifacts": ["docs/designs/example.md"],
                "source_evidence_anchors": [
                    {"kind": "artifact_excerpt", "ref": "docs/designs/example.md#decision"}
                ],
                "match_reasons": ["artifact:docs/designs/example.md"],
                "status": "pending_review",
                "priority_score": 0.9,
                "title": title,
                "summary": "Summary",
                "content": "Body",
                "tags": tags or ["memory", "abandon"],
            }
        )
        candidate_store.store_batch(
            {
                "batch_id": "batch-001",
                "session_id": "session-001",
                "status": "pending_review",
                "trigger": "session_archived",
                "candidate_ids": [candidate_id],
                "truncated_count": 0,
                "evaluation_summary": "evaluated_with_candidates",
                "created_at": "2026-04-18T10:00:00",
                "metadata": {},
            }
        )
        return candidate_store, garage_dir, storage

    def _seed_existing_published_entry_with_same_title(
        self,
        garage_dir: Path,
        title: str,
        tags: list[str],
    ) -> str:
        """Plant a v1-published KnowledgeEntry with a different id but same
        title/tags so ConflictDetector surfaces it as a real similar entry
        (and is not stripped by F004 self-conflict short-circuit)."""
        from datetime import datetime
        from garage_os.knowledge.knowledge_store import KnowledgeStore
        from garage_os.types import KnowledgeEntry, KnowledgeType

        storage = FileStorage(garage_dir)
        knowledge_store = KnowledgeStore(storage)
        existing_id = "existing-conflict-target"
        knowledge_store.store(
            KnowledgeEntry(
                id=existing_id,
                type=KnowledgeType.DECISION,
                topic=title,
                date=datetime.now(),
                tags=list(tags),
                content="Pre-existing entry to force a real conflict.",
            )
        )
        return existing_id

    def test_memory_review_abandon_writes_resolution_abandon_with_null_strategy(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """--action=abandon path -> confirmation resolution=abandon, conflict_strategy=null (FR-403a verify 1)."""
        main(["init", "--path", str(tmp_path)])
        candidate_store, garage_dir, _ = self._seed_candidate(tmp_path)

        result = main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "abandon",
                "--candidate-id",
                "candidate-001",
                "--path",
                str(tmp_path),
            ]
        )
        assert result == 0
        confirmation = candidate_store.retrieve_confirmation("batch-001")
        assert confirmation is not None
        assert confirmation["resolution"] == "abandon"
        assert confirmation.get("conflict_strategy") in (None,)

    def test_memory_review_accept_with_strategy_abandon_writes_resolution_accept(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """--action=accept --strategy=abandon + real conflict -> resolution=accept,
        conflict_strategy=abandon (FR-403a verify 2)."""
        main(["init", "--path", str(tmp_path)])
        candidate_store, garage_dir, _ = self._seed_candidate(tmp_path)
        self._seed_existing_published_entry_with_same_title(
            garage_dir,
            title="Dual-path abandon candidate",
            tags=["memory", "abandon"],
        )

        result = main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "accept",
                "--candidate-id",
                "candidate-001",
                "--strategy",
                "abandon",
                "--path",
                str(tmp_path),
            ]
        )
        assert result == 0
        confirmation = candidate_store.retrieve_confirmation("batch-001")
        assert confirmation is not None
        assert confirmation["resolution"] == "accept"
        assert confirmation.get("conflict_strategy") == "abandon"
        assert (
            candidate_store.retrieve_candidate("candidate-001")["status"] == "abandoned"
        )

    def test_memory_review_accept_with_abandon_strategy_no_conflict_falls_through_to_publish(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """--action=accept --strategy=abandon + no conflict -> normal publish (FR-403a verify 3)."""
        main(["init", "--path", str(tmp_path)])
        candidate_store, garage_dir, _ = self._seed_candidate(tmp_path)

        result = main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "accept",
                "--candidate-id",
                "candidate-001",
                "--strategy",
                "abandon",
                "--path",
                str(tmp_path),
            ]
        )
        assert result == 0
        confirmation = candidate_store.retrieve_confirmation("batch-001")
        assert confirmation is not None
        assert confirmation["resolution"] == "accept"
        # Strategy was passed but no conflict matched -> behavior matches v1 normal accept.
        assert (
            candidate_store.retrieve_candidate("candidate-001")["status"] == "published"
        )

    def test_memory_review_abandon_outputs_no_pub_marker(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """--action=abandon stdout must contain ABANDONED_NO_PUB marker (FR-403b verify 1)."""
        from garage_os.cli import MEMORY_REVIEW_ABANDONED_NO_PUB

        main(["init", "--path", str(tmp_path)])
        self._seed_candidate(tmp_path)

        main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "abandon",
                "--candidate-id",
                "candidate-001",
                "--path",
                str(tmp_path),
            ]
        )

        captured = capsys.readouterr()
        expected = MEMORY_REVIEW_ABANDONED_NO_PUB.format(cid="candidate-001")
        assert expected in captured.out, (
            f"expected stdout to contain '{expected}'; got: {captured.out}"
        )

    def test_memory_review_conflict_abandon_outputs_conflict_marker(
        self,
        tmp_path: Path,
        capsys,
    ) -> None:
        """--action=accept --strategy=abandon + real conflict stdout must contain ABANDONED_CONFLICT marker
        (FR-403b verify 2)."""
        from garage_os.cli import MEMORY_REVIEW_ABANDONED_CONFLICT

        main(["init", "--path", str(tmp_path)])
        _, garage_dir, _ = self._seed_candidate(tmp_path)
        self._seed_existing_published_entry_with_same_title(
            garage_dir,
            title="Dual-path abandon candidate",
            tags=["memory", "abandon"],
        )

        main(
            [
                "memory",
                "review",
                "batch-001",
                "--action",
                "accept",
                "--candidate-id",
                "candidate-001",
                "--strategy",
                "abandon",
                "--path",
                str(tmp_path),
            ]
        )

        captured = capsys.readouterr()
        expected = MEMORY_REVIEW_ABANDONED_CONFLICT.format(cid="candidate-001")
        assert expected in captured.out, (
            f"expected stdout to contain '{expected}'; got: {captured.out}"
        )

    def test_memory_review_two_abandon_markers_do_not_overlap(self) -> None:
        """The two stdout markers must be independently grep-able (FR-403b verify 3)."""
        from garage_os.cli import (
            MEMORY_REVIEW_ABANDONED_CONFLICT,
            MEMORY_REVIEW_ABANDONED_NO_PUB,
        )

        no_pub = MEMORY_REVIEW_ABANDONED_NO_PUB.format(cid="x")
        conflict = MEMORY_REVIEW_ABANDONED_CONFLICT.format(cid="x")
        # Neither rendered marker should be a substring of the other.
        assert no_pub not in conflict
        assert conflict not in no_pub


class TestKnowledgeCommand:
    """Test knowledge search and list commands."""

    def test_knowledge_search(self, tmp_path: Path, capsys) -> None:
        """knowledge search should find matching entries."""
        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Create a knowledge entry
        knowledge_decisions = garage_dir / "knowledge" / "decisions"
        knowledge_decisions.mkdir(parents=True, exist_ok=True)
        (knowledge_decisions / "decision-001.md").write_text(
            """---
id: decision-001
type: decision
topic: Use REST API
date: 2025-01-15T10:00:00
tags: [api, rest]
status: active
version: 1
---

Decided to use REST API for this service.
""",
            encoding="utf-8",
        )

        # Search for the entry
        main(["knowledge", "search", "REST", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert "Found 1 knowledge entry" in captured.out
        assert "[DECISION] Use REST API" in captured.out
        assert "ID: decision-001" in captured.out
        assert "Tags: api, rest" in captured.out

    def test_knowledge_list(self, tmp_path: Path, capsys) -> None:
        """knowledge list should show all entries."""
        # First init
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"

        # Create multiple knowledge entries
        knowledge_decisions = garage_dir / "knowledge" / "decisions"
        knowledge_patterns = garage_dir / "knowledge" / "patterns"

        knowledge_decisions.mkdir(parents=True, exist_ok=True)
        knowledge_patterns.mkdir(parents=True, exist_ok=True)

        (knowledge_decisions / "decision-001.md").write_text(
            """---
id: decision-001
type: decision
topic: Use TypeScript
date: 2025-01-15T10:00:00
tags: [typescript]
status: active
version: 1
---

Decided to use TypeScript.
""",
            encoding="utf-8",
        )

        (knowledge_patterns / "pattern-001.md").write_text(
            """---
id: pattern-001
type: pattern
topic: Repository Pattern
date: 2025-01-16T10:00:00
tags: [design-pattern]
status: active
version: 1
---

Repository pattern implementation.
""",
            encoding="utf-8",
        )

        # List all entries
        main(["knowledge", "list", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert "Total 2 knowledge entry" in captured.out
        assert "[DECISION] Use TypeScript" in captured.out
        assert "[PATTERN] Repository Pattern" in captured.out

    def test_knowledge_empty(self, tmp_path: Path, capsys) -> None:
        """knowledge commands should show 'No knowledge entries' when empty."""
        # First init
        main(["init", "--path", str(tmp_path)])

        # List when empty
        main(["knowledge", "list", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert "No knowledge entries" in captured.out

        # Search when empty
        main(["knowledge", "search", "test", "--path", str(tmp_path)])

        captured = capsys.readouterr()
        assert "No knowledge entries" in captured.out


# ---------------------------------------------------------------------------
# F005 — Knowledge / Experience authoring CLI
# ---------------------------------------------------------------------------

import pytest
import time as _time_mod
from datetime import datetime, timedelta

from garage_os.cli import (
    CLI_SOURCE_EXPERIENCE_ADD,
    CLI_SOURCE_KNOWLEDGE_ADD,
    CLI_SOURCE_KNOWLEDGE_EDIT,
    EXPERIENCE_ADDED_FMT,
    EXPERIENCE_DELETED_FMT,
    EXPERIENCE_NOT_FOUND_FMT,
    ERR_ADD_REQUIRES_CONTENT,
    ERR_CONTENT_AND_FILE_MUTEX,
    ERR_EDIT_REQUIRES_FIELD,
    ERR_FILE_NOT_FOUND_FMT,
    ERR_NO_GARAGE,
    KNOWLEDGE_ADDED_FMT,
    KNOWLEDGE_ALREADY_EXISTS_FMT,
    KNOWLEDGE_DELETED_FMT,
    KNOWLEDGE_EDITED_FMT,
    KNOWLEDGE_NOT_FOUND_FMT,
    _generate_entry_id,
    _generate_experience_id,
)
from garage_os.knowledge.experience_index import ExperienceIndex
from garage_os.knowledge.knowledge_store import KnowledgeStore
from garage_os.storage import FileStorage
from garage_os.types import KnowledgeType


def _read_decision(garage_dir: Path, eid: str) -> dict:
    """Helper: read a decision entry's front matter as dict."""
    storage = FileStorage(garage_dir)
    store = KnowledgeStore(storage)
    entry = store.retrieve(KnowledgeType.DECISION, eid)
    assert entry is not None, f"entry {eid} missing"
    return {
        "id": entry.id,
        "type": entry.type.value,
        "topic": entry.topic,
        "tags": entry.tags,
        "version": entry.version,
        "status": entry.status,
        "content": entry.content,
        "source_artifact": entry.source_artifact,
        "date": entry.date,
        "published_from_candidate": entry.published_from_candidate,
    }


class TestKnowledgeAdd:
    """T1 / FR-501 / FR-502 / FR-508 / FR-509."""

    def test_add_happy_path_writes_entry_with_source_marker(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "Pick SQLite over Postgres",
                "--content",
                "Postgres needs a daemon",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        # find the eid from stdout
        assert "Knowledge entry '" in out
        eid = out.split("'")[1]
        assert eid.startswith("decision-")

        garage_dir = tmp_path / ".garage"
        fm = _read_decision(garage_dir, eid)
        assert fm["topic"] == "Pick SQLite over Postgres"
        assert fm["content"] == "Postgres needs a daemon"
        assert fm["status"] == "active"
        assert fm["version"] == 1
        assert fm["source_artifact"] == CLI_SOURCE_KNOWLEDGE_ADD
        assert fm["tags"] == []

        # KnowledgeStore writes <type>-<entry.id>.md; entry.id already starts
        # with the type prefix from FR-508, so the on-disk file name is e.g.
        # decision-decision-YYYYMMDD-XXXXXX.md. This is intentional (we keep
        # KnowledgeStore's existing file-naming contract untouched per CON-502).
        assert (garage_dir / "knowledge" / "decisions" / f"decision-{eid}.md").is_file()

    def test_add_with_tags_writes_tag_list(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "x",
                "--content",
                "y",
                "--tags",
                "a, b ,c",
                "--path",
                str(tmp_path),
            ]
        )
        eid = capsys.readouterr().out.split("'")[1]
        fm = _read_decision(tmp_path / ".garage", eid)
        assert fm["tags"] == ["a", "b", "c"]

    def test_add_with_explicit_id(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "x",
                "--content",
                "y",
                "--id",
                "custom-001",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Knowledge entry 'custom-001' added" in out
        # File name = decision-<entry.id>.md per KnowledgeStore.store(). Since
        # explicit --id is "custom-001" (no type prefix), the file is
        # decision-custom-001.md.
        assert (
            tmp_path / ".garage" / "knowledge" / "decisions" / "decision-custom-001.md"
        ).is_file()

    def test_add_from_file(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        body = "long body\nwith multiple lines\n"
        body_file = tmp_path / "body.md"
        body_file.write_text(body, encoding="utf-8")
        main(
            [
                "knowledge",
                "add",
                "--type",
                "pattern",
                "--topic",
                "Front-matter pattern",
                "--from-file",
                str(body_file),
                "--path",
                str(tmp_path),
            ]
        )
        out = capsys.readouterr().out
        eid = out.split("'")[1]
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry = store.retrieve(KnowledgeType.PATTERN, eid)
        assert entry is not None
        assert entry.content == body  # CON-505 byte-equality

    def test_add_mutex_content_and_file(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        body = tmp_path / "body.md"
        body.write_text("x", encoding="utf-8")
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "x",
                "--content",
                "y",
                "--from-file",
                str(body),
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert ERR_CONTENT_AND_FILE_MUTEX in err

    def test_add_requires_content_or_file(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "x",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert ERR_ADD_REQUIRES_CONTENT in err

    def test_add_from_file_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        missing = tmp_path / "missing.md"
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "x",
                "--from-file",
                str(missing),
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert ERR_FILE_NOT_FOUND_FMT.format(path=missing) in err

    def test_add_no_garage_dir(self, tmp_path: Path, capsys) -> None:
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "x",
                "--content",
                "y",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert ERR_NO_GARAGE in err

    def test_add_id_collision_same_second(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        fixed = datetime(2026, 4, 19, 12, 0, 0)
        monkeypatch.setattr("garage_os.cli._now_default", lambda: fixed)

        rc1 = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "X",
                "--content",
                "Y",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc1 == 0
        first_out = capsys.readouterr().out
        eid = first_out.split("'")[1]

        rc2 = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "X",
                "--content",
                "Y",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc2 == 1
        err = capsys.readouterr().err
        assert KNOWLEDGE_ALREADY_EXISTS_FMT.format(eid=eid) in err

        # First entry must NOT be overwritten
        fm = _read_decision(tmp_path / ".garage", eid)
        assert fm["topic"] == "X"
        assert fm["content"] == "Y"

    def test_add_explicit_id_collision(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        argv = [
            "knowledge",
            "add",
            "--type",
            "decision",
            "--topic",
            "x",
            "--content",
            "y",
            "--id",
            "dup",
            "--path",
            str(tmp_path),
        ]
        rc1 = main(argv)
        assert rc1 == 0
        out1 = capsys.readouterr().out
        assert "Knowledge entry 'dup' added" in out1
        rc2 = main(argv)
        assert rc2 == 1
        err2 = capsys.readouterr().err
        assert KNOWLEDGE_ALREADY_EXISTS_FMT.format(eid="dup") in err2

    def test_generate_entry_id_format(self) -> None:
        now = datetime(2026, 4, 19, 12, 0, 0)
        eid = _generate_entry_id(KnowledgeType.DECISION, "topic", "content", now)
        assert eid.startswith("decision-20260419-")
        assert len(eid.split("-")[-1]) == 6
        # Same inputs same second → same id
        assert (
            _generate_entry_id(KnowledgeType.DECISION, "topic", "content", now) == eid
        )
        # Different second → different id
        next_sec = now + timedelta(seconds=1)
        assert (
            _generate_entry_id(KnowledgeType.DECISION, "topic", "content", next_sec)
            != eid
        )


class TestKnowledgeEdit:
    """T2 / FR-503 / FR-509 / CON-503 (v1.1 version+=1)."""

    def _add(self, tmp_path: Path, capsys) -> str:
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "Original",
                "--content",
                "Body v1",
                "--tags",
                "a",
                "--path",
                str(tmp_path),
            ]
        )
        out = capsys.readouterr().out
        return out.split("'")[1]

    def test_edit_overlays_only_specified_fields_and_bumps_version(
        self, tmp_path: Path, capsys
    ) -> None:
        eid = self._add(tmp_path, capsys)
        rc = main(
            [
                "knowledge",
                "edit",
                "--type",
                "decision",
                "--id",
                eid,
                "--tags",
                "a,b",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert KNOWLEDGE_EDITED_FMT.format(eid=eid, version=2) in out

        fm = _read_decision(tmp_path / ".garage", eid)
        assert fm["tags"] == ["a", "b"]
        assert fm["topic"] == "Original"  # untouched
        assert fm["content"] == "Body v1"  # untouched
        assert fm["version"] == 2  # CON-503 v1.1 invariant carried into CLI
        assert fm["source_artifact"] == CLI_SOURCE_KNOWLEDGE_EDIT  # FR-509

    def test_edit_requires_at_least_one_field(self, tmp_path: Path, capsys) -> None:
        eid = self._add(tmp_path, capsys)
        rc = main(
            [
                "knowledge",
                "edit",
                "--type",
                "decision",
                "--id",
                eid,
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert ERR_EDIT_REQUIRES_FIELD in capsys.readouterr().err

    def test_edit_mutex_content_and_file(self, tmp_path: Path, capsys) -> None:
        eid = self._add(tmp_path, capsys)
        body = tmp_path / "body.md"
        body.write_text("x", encoding="utf-8")
        rc = main(
            [
                "knowledge",
                "edit",
                "--type",
                "decision",
                "--id",
                eid,
                "--content",
                "y",
                "--from-file",
                str(body),
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        assert ERR_CONTENT_AND_FILE_MUTEX in capsys.readouterr().err

    def test_edit_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(
            [
                "knowledge",
                "edit",
                "--type",
                "decision",
                "--id",
                "missing",
                "--topic",
                "X",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert KNOWLEDGE_NOT_FOUND_FMT.format(eid="missing") in err

    def test_edit_monotonic_version(self, tmp_path: Path, capsys) -> None:
        eid = self._add(tmp_path, capsys)
        for expected in (2, 3, 4):
            main(
                [
                    "knowledge",
                    "edit",
                    "--type",
                    "decision",
                    "--id",
                    eid,
                    "--status",
                    f"v{expected}",
                    "--path",
                    str(tmp_path),
                ]
            )
            out = capsys.readouterr().out
            assert KNOWLEDGE_EDITED_FMT.format(eid=eid, version=expected) in out

    def test_edit_does_not_pollute_publisher_metadata(
        self, tmp_path: Path
    ) -> None:
        """Verify CLI edit only overwrites source_artifact, leaving publisher
        provenance fields (published_from_candidate etc.) intact."""
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"
        storage = FileStorage(garage_dir)
        store = KnowledgeStore(storage)
        # Simulate a publisher-written entry: source_artifact is some
        # publisher-shaped string (not "cli:..."); published_from_candidate set.
        from garage_os.types import KnowledgeEntry
        from datetime import datetime as _dt

        publisher_entry = KnowledgeEntry(
            id="pub-1",
            type=KnowledgeType.DECISION,
            topic="from publisher",
            date=_dt(2026, 1, 1),
            tags=["pub"],
            content="publisher body",
            status="active",
            version=1,
            source_artifact="published_by:F003",
            published_from_candidate="cand-x",
        )
        store.store(publisher_entry)

        rc = main(
            [
                "knowledge",
                "edit",
                "--type",
                "decision",
                "--id",
                "pub-1",
                "--tags",
                "pub,extra",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        fm = _read_decision(garage_dir, "pub-1")
        assert fm["source_artifact"] == CLI_SOURCE_KNOWLEDGE_EDIT
        assert fm["published_from_candidate"] == "cand-x"  # publisher metadata preserved


class TestKnowledgeShow:
    """T3 / FR-504."""

    def test_show_happy(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "knowledge",
                "add",
                "--type",
                "solution",
                "--topic",
                "Showme",
                "--content",
                "Hello",
                "--tags",
                "a,b",
                "--id",
                "s1",
                "--path",
                str(tmp_path),
            ]
        )
        capsys.readouterr()
        rc = main(["knowledge", "show", "--type", "solution", "--id", "s1", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "id: s1" in out
        assert "topic: Showme" in out
        assert "version: 1" in out
        assert f"source_artifact: {CLI_SOURCE_KNOWLEDGE_ADD}" in out
        assert "tags: a, b" in out
        assert "Hello" in out
        # Front matter must come before the body, separated by a blank line
        # (TT4 reviewer feedback: ordering not previously asserted).
        front_idx = out.index("source_artifact:")
        body_idx = out.index("Hello")
        assert front_idx < body_idx
        assert "\n\nHello" in out

    def test_show_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(["knowledge", "show", "--type", "solution", "--id", "missing", "--path", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert KNOWLEDGE_NOT_FOUND_FMT.format(eid="missing") in err


class TestKnowledgeDelete:
    """T3 / FR-505."""

    def test_delete_happy(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "knowledge",
                "add",
                "--type",
                "pattern",
                "--topic",
                "del",
                "--content",
                "x",
                "--id",
                "p1",
                "--path",
                str(tmp_path),
            ]
        )
        capsys.readouterr()
        path = tmp_path / ".garage" / "knowledge" / "patterns" / "pattern-p1.md"
        assert path.is_file()
        rc = main(["knowledge", "delete", "--type", "pattern", "--id", "p1", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert KNOWLEDGE_DELETED_FMT.format(eid="p1") in out
        assert not path.is_file()

    def test_delete_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(["knowledge", "delete", "--type", "pattern", "--id", "missing", "--path", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert KNOWLEDGE_NOT_FOUND_FMT.format(eid="missing") in err


class TestExperienceAdd:
    """T4 / FR-506 / FR-508 experience / FR-509."""

    def test_experience_add_happy(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(
            [
                "experience",
                "add",
                "--task-type",
                "spike",
                "--skill",
                "ahe-design",
                "--skill",
                "ahe-tasks",
                "--domain",
                "platform",
                "--outcome",
                "success",
                "--duration",
                "1800",
                "--complexity",
                "medium",
                "--summary",
                "Tried SQLite path",
                "--tech",
                "python",
                "--tech",
                "sqlite",
                "--tags",
                "indexing,storage",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Experience record '" in out
        rid = out.split("'")[1]
        record_path = tmp_path / ".garage" / "experience" / "records" / f"{rid}.json"
        assert record_path.is_file()
        data = json.loads(record_path.read_text(encoding="utf-8"))
        assert data["record_id"] == rid
        assert data["task_type"] == "spike"
        assert data["skill_ids"] == ["ahe-design", "ahe-tasks"]
        assert data["outcome"] == "success"
        assert data["duration_seconds"] == 1800
        assert data["complexity"] == "medium"
        assert data["lessons_learned"] == ["Tried SQLite path"]
        assert data["tech_stack"] == ["python", "sqlite"]
        assert data["key_patterns"] == ["indexing", "storage"]
        assert data["problem_domain"] == "spike"  # default
        # FR-509 / ADR-503: source marker via "cli:" prefix at artifacts[0]
        assert data["artifacts"][0] == CLI_SOURCE_EXPERIENCE_ADD
        assert data["artifacts"][0].startswith("cli:")

    def test_experience_add_outcome_must_be_valid(self, tmp_path: Path) -> None:
        main(["init", "--path", str(tmp_path)])
        with pytest.raises(SystemExit) as exc:
            main(
                [
                    "experience",
                    "add",
                    "--task-type",
                    "spike",
                    "--skill",
                    "x",
                    "--domain",
                    "d",
                    "--outcome",
                    "garbage",
                    "--duration",
                    "10",
                    "--complexity",
                    "low",
                    "--summary",
                    "s",
                    "--path",
                    str(tmp_path),
                ]
            )
        assert exc.value.code == 2

    def test_generate_experience_id_format(self) -> None:
        now = datetime(2026, 4, 19, 12, 0, 0)
        rid = _generate_experience_id("spike", "summary", now)
        assert rid.startswith("exp-20260419-")
        assert len(rid.split("-")[-1]) == 6
        # Same inputs same second → same id
        assert _generate_experience_id("spike", "summary", now) == rid
        # Different second → different id (time salt is part of the input)
        next_sec = now + timedelta(seconds=1)
        assert _generate_experience_id("spike", "summary", next_sec) != rid

    def test_experience_add_id_collision_same_second(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        """FR-508 experience-branch parity with knowledge add collision."""
        main(["init", "--path", str(tmp_path)])
        fixed = datetime(2026, 4, 19, 12, 0, 0)
        monkeypatch.setattr("garage_os.cli._now_default", lambda: fixed)
        argv = [
            "experience",
            "add",
            "--task-type",
            "spike",
            "--skill",
            "x",
            "--domain",
            "d",
            "--outcome",
            "success",
            "--duration",
            "10",
            "--complexity",
            "low",
            "--summary",
            "same",
            "--path",
            str(tmp_path),
        ]
        rc1 = main(argv)
        assert rc1 == 0
        rc2 = main(argv)
        assert rc2 == 1
        err = capsys.readouterr().err
        assert "already exists" in err


class TestExperienceShow:
    """T5 / FR-507a."""

    def test_experience_show_happy(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "experience",
                "add",
                "--task-type",
                "spike",
                "--skill",
                "x",
                "--domain",
                "d",
                "--outcome",
                "success",
                "--duration",
                "10",
                "--complexity",
                "low",
                "--summary",
                "s",
                "--id",
                "exp-1",
                "--path",
                str(tmp_path),
            ]
        )
        capsys.readouterr()
        rc = main(["experience", "show", "--id", "exp-1", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["record_id"] == "exp-1"
        assert data["task_type"] == "spike"
        assert data["outcome"] == "success"

    def test_experience_show_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(["experience", "show", "--id", "missing", "--path", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert EXPERIENCE_NOT_FOUND_FMT.format(rid="missing") in err


class TestExperienceDelete:
    """T5 / FR-507b — must also prune the central index."""

    def test_experience_delete_happy_and_prunes_index(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "experience",
                "add",
                "--task-type",
                "spike",
                "--skill",
                "x",
                "--domain",
                "d",
                "--outcome",
                "success",
                "--duration",
                "10",
                "--complexity",
                "low",
                "--summary",
                "s",
                "--id",
                "exp-1",
                "--path",
                str(tmp_path),
            ]
        )
        capsys.readouterr()
        garage_dir = tmp_path / ".garage"
        index_path = garage_dir / "knowledge" / ".metadata" / "index.json"
        assert index_path.is_file()
        index_before = json.loads(index_path.read_text(encoding="utf-8"))
        assert "exp-1" in index_before

        rc = main(["experience", "delete", "--id", "exp-1", "--path", str(tmp_path)])
        assert rc == 0
        assert EXPERIENCE_DELETED_FMT.format(rid="exp-1") in capsys.readouterr().out
        assert not (garage_dir / "experience" / "records" / "exp-1.json").is_file()
        index_after = json.loads(index_path.read_text(encoding="utf-8"))
        assert "exp-1" not in index_after  # FR-507b key assertion

        # Following show must report not-found
        rc2 = main(["experience", "show", "--id", "exp-1", "--path", str(tmp_path)])
        assert rc2 == 1

    def test_experience_delete_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        rc = main(["experience", "delete", "--id", "missing", "--path", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert EXPERIENCE_NOT_FOUND_FMT.format(rid="missing") in err


class TestKnowledgeAuthoringCrossCutting:
    """T6 cross-cutting: help self-description, CRUD loop, smoke perf,
    and FR-509 source-marker namespace.
    """

    def test_knowledge_help_lists_all_subcommands(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["knowledge", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        for sub in ("search", "list", "add", "edit", "show", "delete"):
            assert sub in out

    def test_experience_help_lists_all_subcommands(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["experience", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        for sub in ("add", "show", "delete"):
            assert sub in out

    def test_knowledge_add_help_lists_all_args(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["knowledge", "add", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        for arg in ("--type", "--topic", "--tags", "--content", "--from-file", "--id"):
            assert arg in out

    def test_crud_loop(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        # add
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "T",
                "--content",
                "C",
                "--id",
                "loop-1",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        capsys.readouterr()

        # show
        assert (
            main(
                ["knowledge", "show", "--type", "decision", "--id", "loop-1", "--path", str(tmp_path)]
            )
            == 0
        )
        capsys.readouterr()

        # edit
        assert (
            main(
                [
                    "knowledge",
                    "edit",
                    "--type",
                    "decision",
                    "--id",
                    "loop-1",
                    "--topic",
                    "T2",
                    "--path",
                    str(tmp_path),
                ]
            )
            == 0
        )
        capsys.readouterr()

        # show again — version should be 2 and topic T2
        rc = main(
            ["knowledge", "show", "--type", "decision", "--id", "loop-1", "--path", str(tmp_path)]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "topic: T2" in out
        assert "version: 2" in out

        # delete
        assert (
            main(
                ["knowledge", "delete", "--type", "decision", "--id", "loop-1", "--path", str(tmp_path)]
            )
            == 0
        )
        capsys.readouterr()

        # show after delete → 1
        assert (
            main(
                ["knowledge", "show", "--type", "decision", "--id", "loop-1", "--path", str(tmp_path)]
            )
            == 1
        )

    def test_add_smoke_under_one_second(self, tmp_path: Path, capsys) -> None:
        """NFR-503: a single `add` round-trip should take well under 1.0s."""
        main(["init", "--path", str(tmp_path)])
        capsys.readouterr()
        start = _time_mod.monotonic()
        rc = main(
            [
                "knowledge",
                "add",
                "--type",
                "decision",
                "--topic",
                "perf",
                "--content",
                "x",
                "--id",
                "perf-1",
                "--path",
                str(tmp_path),
            ]
        )
        elapsed = _time_mod.monotonic() - start
        assert rc == 0
        capsys.readouterr()
        assert elapsed < 1.0, f"add took {elapsed:.3f}s (>= 1.0s)"

    def test_cli_source_markers_use_cli_namespace(self) -> None:
        """ADR-503: every CLI source marker must start with 'cli:'."""
        for marker in (
            CLI_SOURCE_KNOWLEDGE_ADD,
            CLI_SOURCE_KNOWLEDGE_EDIT,
            CLI_SOURCE_EXPERIENCE_ADD,
        ):
            assert marker.startswith("cli:")


# ---------------------------------------------------------------------------
# F006 — Recall & Knowledge Graph
# ---------------------------------------------------------------------------

from garage_os.cli import (  # noqa: E402
    CLI_SOURCE_KNOWLEDGE_LINK,
    ERR_LINK_FROM_AMBIGUOUS_FMT,
    GRAPH_EDGE_NONE,
    GRAPH_INCOMING_HEADER,
    GRAPH_OUTGOING_HEADER,
    KNOWLEDGE_LINKED_FMT,
    KNOWLEDGE_LINK_ALREADY_FMT,
    RECOMMEND_NO_RESULTS_FMT,
    _recommend_experience,
    _resolve_knowledge_entry_unique,
)
from garage_os.memory.recommendation_service import RecommendationContextBuilder  # noqa: E402


def _add_knowledge(
    tmp_path: Path,
    *,
    type_: str,
    eid: str,
    topic: str = "topic",
    content: str = "content",
    tags: str | None = None,
) -> None:
    """Test helper: add a knowledge entry via the CLI add path."""
    argv = [
        "knowledge",
        "add",
        "--type",
        type_,
        "--topic",
        topic,
        "--content",
        content,
        "--id",
        eid,
        "--path",
        str(tmp_path),
    ]
    if tags is not None:
        argv.extend(["--tags", tags])
    rc = main(argv)
    assert rc == 0, f"add failed for ({type_}, {eid})"


class TestResolveKnowledgeEntryUnique:
    """T1 / FR-605 helper layer."""

    def test_resolve_unique_hit(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="A")
        capsys.readouterr()
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry, types = _resolve_knowledge_entry_unique(store, "A")
        assert types == ["decision"]
        assert entry is not None
        assert entry.id == "A"

    def test_resolve_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        capsys.readouterr()
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry, types = _resolve_knowledge_entry_unique(store, "missing")
        assert types == []
        assert entry is None

    def test_resolve_ambiguous(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="X")
        _add_knowledge(tmp_path, type_="pattern", eid="X")
        capsys.readouterr()
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry, types = _resolve_knowledge_entry_unique(store, "X")
        assert len(types) >= 2
        assert "decision" in types
        assert "pattern" in types
        # First hit follows KnowledgeType enum order (decision first)
        assert entry is not None
        assert entry.type.value == "decision"


class TestRecommendExperienceHelper:
    """T1 / FR-602 helper layer (pure function, no FS dependency)."""

    def _make_record(self, **overrides):
        from garage_os.types import ExperienceRecord
        from datetime import datetime as _dt

        defaults = dict(
            record_id="exp-1",
            task_type="spike",
            skill_ids=["x"],
            tech_stack=["sqlite"],
            domain="platform",
            problem_domain="storage",
            outcome="success",
            duration_seconds=10,
            complexity="low",
            session_id="sess-1",
            artifacts=["cli:experience-add"],
            key_patterns=["indexing"],
            lessons_learned=["Tried SQLite indexing"],
            pitfalls=[],
            recommendations=[],
            created_at=_dt(2026, 1, 1),
            updated_at=_dt(2026, 1, 1),
        )
        defaults.update(overrides)
        return ExperienceRecord(**defaults)

    def test_domain_match(self) -> None:
        record = self._make_record()
        results = _recommend_experience(
            [record],
            {"domain": "platform", "tags": []},
        )
        assert len(results) == 1
        assert results[0]["score"] >= 0.8
        assert any(r.startswith("domain:") for r in results[0]["match_reasons"])

    def test_problem_domain_match(self) -> None:
        record = self._make_record()
        results = _recommend_experience(
            [record],
            {"problem_domain": "storage", "tags": []},
        )
        assert results
        assert any(
            r.startswith("problem_domain:") for r in results[0]["match_reasons"]
        )

    def test_task_type_via_tag_token(self) -> None:
        record = self._make_record(task_type="bugfix")
        results = _recommend_experience(
            [record],
            {"tags": ["bug"]},
        )
        assert results
        assert any(r.startswith("task_type:") for r in results[0]["match_reasons"])

    def test_tech_stack_via_tag_token(self) -> None:
        record = self._make_record()
        results = _recommend_experience(
            [record],
            {"tags": ["sqlite"]},
        )
        assert results
        assert any(r.startswith("tech:") for r in results[0]["match_reasons"])

    def test_key_patterns_via_tag_token(self) -> None:
        record = self._make_record()
        results = _recommend_experience(
            [record],
            {"tags": ["indexing"]},
        )
        assert results
        assert any(r.startswith("pattern:") for r in results[0]["match_reasons"])

    def test_lesson_text_match(self) -> None:
        record = self._make_record()
        results = _recommend_experience(
            [record],
            {"tags": ["sqlite"]},
        )
        # token "sqlite" hits both tech_stack (0.6) and lesson-text (0.4)
        reasons = results[0]["match_reasons"]
        assert any(r.startswith("lesson-text:") for r in reasons)

    def test_no_match_excluded(self) -> None:
        record = self._make_record(domain="other")
        results = _recommend_experience(
            [record],
            {"tags": ["wholly-unrelated"]},
        )
        assert results == []

    def test_returned_shape_matches_recommendation_service(self) -> None:
        record = self._make_record()
        results = _recommend_experience(
            [record],
            {"domain": "platform", "tags": []},
        )
        item = results[0]
        for key in ("entry_id", "entry_type", "title", "score", "match_reasons", "source_session"):
            assert key in item
        assert item["entry_type"] == "experience"
        assert item["entry_id"] == "exp-1"
        assert item["source_session"] == "sess-1"

    def test_title_falls_back_to_task_type(self) -> None:
        record = self._make_record(lessons_learned=[])
        results = _recommend_experience(
            [record],
            {"domain": "platform", "tags": []},
        )
        assert results[0]["title"] == "spike"


class TestRecommend:
    """T2 / FR-601 / FR-602 / FR-603 (handler + sub-parser)."""

    def test_recommend_knowledge_only_happy(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(
            tmp_path,
            type_="decision",
            eid="d1",
            topic="auth jwt expiry",
            tags="auth",
        )
        capsys.readouterr()
        rc = main(["recommend", "auth", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "[DECISION]" in out
        assert "ID: d1" in out
        assert "Score:" in out
        assert "Match:" in out
        assert "tag:auth" in out

    def test_recommend_experience_only(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "experience",
                "add",
                "--task-type",
                "spike",
                "--skill",
                "x",
                "--domain",
                "platform",
                "--outcome",
                "success",
                "--duration",
                "10",
                "--complexity",
                "low",
                "--summary",
                "Tried SQLite indexing",
                "--id",
                "exp-1",
                "--path",
                str(tmp_path),
            ]
        )
        capsys.readouterr()
        rc = main(["recommend", "indexing", "--domain", "platform", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "[EXPERIENCE]" in out
        assert "ID: exp-1" in out
        assert "Match:" in out

    def test_recommend_mixed_sorted_by_score(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(
            tmp_path,
            type_="decision",
            eid="d1",
            topic="auth jwt",
            tags="auth",
        )
        main(
            [
                "experience",
                "add",
                "--task-type",
                "auth",
                "--skill",
                "x",
                "--domain",
                "platform",
                "--outcome",
                "success",
                "--duration",
                "10",
                "--complexity",
                "low",
                "--summary",
                "auth flow",
                "--id",
                "exp-auth",
                "--path",
                str(tmp_path),
            ]
        )
        capsys.readouterr()
        rc = main(["recommend", "auth", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        # Both halves should appear
        assert "[DECISION]" in out
        assert "[EXPERIENCE]" in out

    def test_recommend_top_limits_results(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        for i in range(3):
            _add_knowledge(
                tmp_path,
                type_="decision",
                eid=f"d{i}",
                topic="auth",
                tags="auth",
            )
        capsys.readouterr()
        rc = main(["recommend", "auth", "--top", "2", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert out.count("[DECISION]") == 2

    def test_recommend_tag_and_domain_passed_through(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(
            tmp_path, type_="decision", eid="d1", topic="api rest", tags="api,rest"
        )
        capsys.readouterr()
        rc = main(
            [
                "recommend",
                "rate",
                "--tag",
                "api",
                "--tag",
                "rest",
                "--domain",
                "platform",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "[DECISION]" in out
        assert "tag:api" in out
        assert "tag:rest" in out

    def test_recommend_zero_results_on_empty_garage(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        capsys.readouterr()
        rc = main(["recommend", "anything", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert RECOMMEND_NO_RESULTS_FMT.format(query="anything") in out

    def test_recommend_zero_results_with_entries_but_no_match(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        for i in range(3):
            _add_knowledge(
                tmp_path,
                type_="decision",
                eid=f"d{i}",
                topic="storage",
                tags="storage",
            )
        capsys.readouterr()
        rc = main(["recommend", "completely-unrelated", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert RECOMMEND_NO_RESULTS_FMT.format(query="completely-unrelated") in out

    def test_recommend_no_garage_dir(self, tmp_path: Path, capsys) -> None:
        rc = main(["recommend", "anything", "--path", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert "No .garage/" in err

    def test_build_from_query_shape(self) -> None:
        builder = RecommendationContextBuilder()
        ctx = builder.build_from_query("auth jwt expiry", tags=["api"], domain="platform")
        assert ctx["session_topic"] == "auth jwt expiry"
        assert ctx["domain"] == "platform"
        assert ctx["problem_domain"] is None
        assert "auth" in ctx["tags"]
        assert "jwt" in ctx["tags"]
        assert "expiry" in ctx["tags"]
        assert "api" in ctx["tags"]
        assert ctx["skill_name"] == "auth"
        # Existing build() method must remain callable + unchanged
        ctx2 = builder.build("some-skill", params={"domain": "x"})
        assert ctx2["skill_name"] == "some-skill"
        assert ctx2["domain"] == "x"


class TestKnowledgeLink:
    """T3 / FR-604 / FR-605 / FR-607."""

    def test_link_happy_appends_and_bumps_version(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="A")
        _add_knowledge(tmp_path, type_="decision", eid="B")
        capsys.readouterr()
        rc = main(
            [
                "knowledge",
                "link",
                "--from",
                "A",
                "--to",
                "B",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert KNOWLEDGE_LINKED_FMT.format(src="A", dst="B", kind="related-decision") in out
        # Disk
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry = store.retrieve(KnowledgeType.DECISION, "A")
        assert entry is not None
        assert entry.related_decisions == ["B"]
        assert entry.version == 2  # CON-603: v1.1 invariant carried into link
        assert entry.source_artifact == CLI_SOURCE_KNOWLEDGE_LINK

    def test_link_repeated_is_idempotent_in_field(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="A")
        capsys.readouterr()
        argv = ["knowledge", "link", "--from", "A", "--to", "B", "--path", str(tmp_path)]
        rc1 = main(argv)
        assert rc1 == 0
        capsys.readouterr()
        rc2 = main(argv)
        assert rc2 == 0
        out = capsys.readouterr().out
        assert KNOWLEDGE_LINK_ALREADY_FMT.format(src="A", dst="B", kind="related-decision") in out
        # Field still deduped
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry = store.retrieve(KnowledgeType.DECISION, "A")
        assert entry is not None
        assert entry.related_decisions == ["B"]
        # source_artifact stays cli:knowledge-link on re-link (overwrite even on no-op)
        assert entry.source_artifact == CLI_SOURCE_KNOWLEDGE_LINK
        # version bumped twice (init add -> v1, link -> v2, re-link -> v3) — by CON-603
        assert entry.version == 3

    def test_link_related_task_writes_separate_field(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="A")
        capsys.readouterr()
        rc = main(
            [
                "knowledge",
                "link",
                "--from",
                "A",
                "--to",
                "T005",
                "--kind",
                "related-task",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry = store.retrieve(KnowledgeType.DECISION, "A")
        assert entry is not None
        assert entry.related_tasks == ["T005"]
        assert entry.related_decisions == []

    def test_link_from_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        capsys.readouterr()
        rc = main(
            [
                "knowledge",
                "link",
                "--from",
                "missing",
                "--to",
                "Y",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Knowledge entry 'missing' not found" in err

    def test_link_to_unvalidated_external_id(
        self, tmp_path: Path, capsys
    ) -> None:
        """FR-604: --to is accepted as any string (e.g. external task IDs)."""
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="A")
        capsys.readouterr()
        rc = main(
            [
                "knowledge",
                "link",
                "--from",
                "A",
                "--to",
                "anything-goes-12345",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0

    def test_link_ambiguous_from_id(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="X")
        _add_knowledge(tmp_path, type_="pattern", eid="X")
        capsys.readouterr()
        rc = main(
            [
                "knowledge",
                "link",
                "--from",
                "X",
                "--to",
                "Y",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "ambiguous" in err.lower()
        assert "decision" in err
        assert "pattern" in err
        # Disk: neither entry mutated
        storage = FileStorage(tmp_path / ".garage")
        store = KnowledgeStore(storage)
        entry_d = store.retrieve(KnowledgeType.DECISION, "X")
        entry_p = store.retrieve(KnowledgeType.PATTERN, "X")
        assert entry_d is not None and entry_d.related_decisions == []
        assert entry_p is not None and entry_p.related_decisions == []

    def test_link_does_not_pollute_publisher_metadata(
        self, tmp_path: Path
    ) -> None:
        """FR-607: link overrides source_artifact but keeps publisher metadata."""
        main(["init", "--path", str(tmp_path)])
        garage_dir = tmp_path / ".garage"
        storage = FileStorage(garage_dir)
        store = KnowledgeStore(storage)
        from garage_os.types import KnowledgeEntry as _KE
        from datetime import datetime as _dt

        publisher_entry = _KE(
            id="P",
            type=KnowledgeType.DECISION,
            topic="from publisher",
            date=_dt(2026, 1, 1),
            tags=[],
            content="body",
            status="active",
            version=1,
            source_artifact="published_by:F003",
            published_from_candidate="cand-x",
        )
        store.store(publisher_entry)

        rc = main(
            [
                "knowledge",
                "link",
                "--from",
                "P",
                "--to",
                "Q",
                "--path",
                str(tmp_path),
            ]
        )
        assert rc == 0
        entry = store.retrieve(KnowledgeType.DECISION, "P")
        assert entry is not None
        assert entry.related_decisions == ["Q"]
        assert entry.source_artifact == CLI_SOURCE_KNOWLEDGE_LINK
        assert entry.published_from_candidate == "cand-x"  # publisher metadata preserved


class TestKnowledgeGraph:
    """T4 / FR-606."""

    def test_graph_node_with_outgoing_and_incoming(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="A", topic="topic-A")
        _add_knowledge(tmp_path, type_="decision", eid="B", topic="topic-B")
        _add_knowledge(tmp_path, type_="pattern", eid="C", topic="topic-C")
        # A -> B; B -> C
        main(["knowledge", "link", "--from", "A", "--to", "B", "--path", str(tmp_path)])
        main(["knowledge", "link", "--from", "B", "--to", "C", "--path", str(tmp_path)])
        capsys.readouterr()

        rc = main(["knowledge", "graph", "--id", "B", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "[DECISION] topic-B" in out
        assert "ID: B" in out
        assert GRAPH_OUTGOING_HEADER in out
        assert "-> C (related-decision)" in out
        assert GRAPH_INCOMING_HEADER in out
        assert "<- A (related-decision)" in out

    def test_graph_isolated_node_shows_none(
        self, tmp_path: Path, capsys
    ) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="iso", topic="alone")
        capsys.readouterr()
        rc = main(["knowledge", "graph", "--id", "iso", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert GRAPH_OUTGOING_HEADER in out
        assert GRAPH_INCOMING_HEADER in out
        # Both edge sections should report (none)
        assert out.count(GRAPH_EDGE_NONE) == 2

    def test_graph_not_found(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        capsys.readouterr()
        rc = main(["knowledge", "graph", "--id", "missing", "--path", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert "Knowledge entry 'missing' not found" in err

    def test_graph_ambiguous_id(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="X")
        _add_knowledge(tmp_path, type_="pattern", eid="X")
        capsys.readouterr()
        rc = main(["knowledge", "graph", "--id", "X", "--path", str(tmp_path)])
        assert rc == 1
        err = capsys.readouterr().err
        assert "ambiguous" in err.lower()

    def test_graph_mixed_edge_kinds(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(tmp_path, type_="decision", eid="A")
        _add_knowledge(tmp_path, type_="decision", eid="B")
        # A -> B (related-decision) AND A -> T005 (related-task)
        main(["knowledge", "link", "--from", "A", "--to", "B", "--path", str(tmp_path)])
        main(
            [
                "knowledge",
                "link",
                "--from",
                "A",
                "--to",
                "T005",
                "--kind",
                "related-task",
                "--path",
                str(tmp_path),
            ]
        )
        capsys.readouterr()
        rc = main(["knowledge", "graph", "--id", "A", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "-> B (related-decision)" in out
        assert "-> T005 (related-task)" in out


class TestRecallAndGraphCrossCutting:
    """T5 cross-cutting: help self-description, smoke perf, source-marker namespace."""

    def test_top_level_help_lists_recommend(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "recommend" in out

    def test_knowledge_help_lists_all_8_subcommands(self, capsys) -> None:
        """FR-608: F005 6 + F006 2 = 8 subcommands must all appear."""
        with pytest.raises(SystemExit) as exc:
            main(["knowledge", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        for sub in ("search", "list", "add", "edit", "show", "delete", "link", "graph"):
            assert sub in out

    def test_recommend_help_lists_all_args(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["recommend", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        for arg in ("query", "--tag", "--domain", "--top"):
            assert arg in out

    def test_link_help_lists_all_args(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["knowledge", "link", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        for arg in ("--from", "--to", "--kind"):
            assert arg in out

    def test_graph_help_lists_all_args(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            main(["knowledge", "graph", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--id" in out

    def test_link_source_marker_uses_cli_namespace(self) -> None:
        """FR-607 / ADR-503 延伸: cli:knowledge-link 必须以 cli: 开头."""
        assert CLI_SOURCE_KNOWLEDGE_LINK.startswith("cli:")

    def test_recommend_prints_source_line_when_present(
        self, tmp_path: Path, capsys
    ) -> None:
        """OQ-607 / test-review TR-1: experience records with session_id should
        produce a `Source: <session>` line in recommend stdout."""
        main(["init", "--path", str(tmp_path)])
        main(
            [
                "experience",
                "add",
                "--task-type",
                "spike",
                "--skill",
                "x",
                "--domain",
                "platform",
                "--outcome",
                "success",
                "--duration",
                "10",
                "--complexity",
                "low",
                "--summary",
                "Tried SQLite indexing",
                "--id",
                "exp-with-session",
                "--path",
                str(tmp_path),
            ]
        )
        # Patch session_id directly in the on-disk JSON (CLI add intentionally
        # leaves session_id="" — F005 _experience_add behavior, see cli.py)
        rec_path = (
            tmp_path / ".garage" / "experience" / "records" / "exp-with-session.json"
        )
        data = json.loads(rec_path.read_text(encoding="utf-8"))
        data["session_id"] = "sess-walkthrough-42"
        rec_path.write_text(json.dumps(data), encoding="utf-8")
        capsys.readouterr()
        rc = main(
            ["recommend", "indexing", "--domain", "platform", "--path", str(tmp_path)]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "Source: sess-walkthrough-42" in out

    def test_recommend_skill_name_only_fallback_prints_uniformly(
        self, tmp_path: Path, capsys
    ) -> None:
        """test-review TR-2 / design §10.1 Note: when match is text-only
        (skill_name token in topic/content but no tag/domain match),
        RecommendationService returns lower-score entries; CLI must still
        render them in the canonical `[TYPE] / ID / Score / Match` block."""
        main(["init", "--path", str(tmp_path)])
        _add_knowledge(
            tmp_path,
            type_="decision",
            eid="d-auth",
            topic="some note about auth",
            tags=None,
        )
        capsys.readouterr()
        rc = main(["recommend", "auth", "--path", str(tmp_path)])
        assert rc == 0
        out = capsys.readouterr().out
        assert "[DECISION]" in out
        assert "ID: d-auth" in out
        assert "Score:" in out
        assert "Match:" in out
        assert "skill" in out.lower()

    def test_recommendation_service_recommend_byte_level_unchanged(self) -> None:
        """test-review TR-3 / CON-605: RecommendationService.recommend()
        signature and ranking weights MUST NOT have been mutated by F006."""
        import inspect
        from garage_os.memory import recommendation_service

        sig = inspect.signature(
            recommendation_service.RecommendationService.recommend
        )
        params = list(sig.parameters)
        assert params == ["self", "context"]
        src = inspect.getsource(
            recommendation_service.RecommendationService.recommend
        )
        for token in (
            "score += 1.0",
            "score += 0.5",
            "score += 0.8",
            "score += 0.6",
            "skill_name_only",
        ):
            assert token in src, (
                f"CON-605 violated: token '{token}' missing from recommend()"
            )

    def test_recommend_smoke_under_one_and_a_half_seconds(
        self, tmp_path: Path, capsys
    ) -> None:
        """NFR-603: a single recommend round-trip must finish well under 1.5s."""
        main(["init", "--path", str(tmp_path)])
        for i in range(10):
            _add_knowledge(
                tmp_path,
                type_="decision",
                eid=f"d{i}",
                topic="auth jwt",
                tags="auth",
            )
        capsys.readouterr()
        start = _time_mod.monotonic()
        rc = main(["recommend", "auth", "--path", str(tmp_path)])
        elapsed = _time_mod.monotonic() - start
        assert rc == 0
        capsys.readouterr()
        assert elapsed < 1.5, f"recommend took {elapsed:.3f}s (>= 1.5s)"


# ---------------------------------------------------------------------------
# F007: garage init --hosts ... (host installer)
# ---------------------------------------------------------------------------


class TestInitWithHosts:
    """F007 T4 — CLI integration for the host installer.

    Backed by the real packs/garage/ pack shipped in T1 so these tests cover
    the production code path end to end (no mocks of install_packs).
    """

    REPO_ROOT = Path(__file__).resolve().parents[1]
    PACKS_ROOT = REPO_ROOT / "packs"

    @staticmethod
    def _link_packs(tmp_path: Path) -> None:
        """Make the real packs/ available inside tmp_path via a symlink.

        Avoids copying so tests stay fast while still exercising the same
        on-disk layout that production uses.
        """
        link = tmp_path / "packs"
        if link.exists() or link.is_symlink():
            return
        link.symlink_to(TestInitWithHosts.PACKS_ROOT)

    def test_default_init_unchanged_when_no_hosts(
        self, tmp_path: Path, capsys
    ) -> None:
        """CON-702: bare `garage init` with no flags must keep F002 behavior.

        Specifically: stdout includes the stable init marker line, and no host
        directory is touched.
        """
        # No packs/ symlink → guarantee zero packs to install even if the
        # interactive prompt accidentally yields hosts.
        rc = main(["init", "--path", str(tmp_path), "--yes"])
        assert rc == 0

        captured = capsys.readouterr()
        assert f"Initialized garage-agent in {tmp_path}/.garage" in captured.out
        # Nothing else relevant on stdout/stderr.
        assert "Installed" not in captured.out

        # No host directories created.
        assert not (tmp_path / ".claude").exists()
        assert not (tmp_path / ".cursor").exists()
        assert not (tmp_path / ".opencode").exists()

    def test_hosts_explicit_list(self, tmp_path: Path, capsys) -> None:
        """`--hosts claude` end-to-end installs the garage pack and prints marker."""
        self._link_packs(tmp_path)
        rc = main(["init", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 0

        # Skill physically present.
        skill = tmp_path / ".claude/skills/garage-hello/SKILL.md"
        assert skill.exists()
        text = skill.read_text(encoding="utf-8")
        assert "name: garage-hello" in text
        assert "installed_by: garage" in text

        # Stable stdout marker (use regex to avoid coupling to the exact
        # number of skills/agents in packs/garage/, which T1 owns).
        import re as _re
        captured = capsys.readouterr()
        assert _re.search(
            r"Installed \d+ skills, \d+ agents into hosts: claude",
            captured.out,
        ), f"marker not found in stdout: {captured.out!r}"

        # Manifest written.
        manifest_path = tmp_path / ".garage" / "config" / "host-installer.json"
        assert manifest_path.is_file()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["installed_hosts"] == ["claude"]
        # F008 carry-forward: packs/ now contains coding + garage + writing;
        # use ⊆ instead of == to keep this F007 test forward-compatible
        # with future pack additions (same intent as test_subprocess_smoke_three_hosts
        # using regex-on-marker pattern).
        assert "garage" in manifest["installed_packs"]

    def test_hosts_all_installs_three_first_class(
        self, tmp_path: Path, capsys
    ) -> None:
        self._link_packs(tmp_path)
        rc = main(["init", "--path", str(tmp_path), "--hosts", "all"])
        assert rc == 0

        assert (tmp_path / ".claude/skills/garage-hello/SKILL.md").exists()
        assert (tmp_path / ".cursor/skills/garage-hello/SKILL.md").exists()
        assert (tmp_path / ".opencode/skills/garage-hello/SKILL.md").exists()
        # Cursor has no agent surface → no .cursor/agent[s]/ directory.
        assert not (tmp_path / ".cursor/agents").exists()
        assert not (tmp_path / ".cursor/agent").exists()

        captured = capsys.readouterr()
        assert "claude" in captured.out
        assert "cursor" in captured.out
        assert "opencode" in captured.out

    def test_unknown_host_exit_1_but_garage_dir_created(
        self, tmp_path: Path, capsys
    ) -> None:
        """FR-702 acceptance #4: unknown host fails 1, but .garage/ still created (CON-702)."""
        self._link_packs(tmp_path)
        rc = main(["init", "--path", str(tmp_path), "--hosts", "notarealtool"])
        assert rc == 1

        captured = capsys.readouterr()
        assert "Unknown host: notarealtool" in captured.err
        # CON-702: legacy structure still created even when host arg is bad.
        assert (tmp_path / ".garage").is_dir()
        assert (tmp_path / ".garage" / "README.md").is_file()

    def test_yes_no_hosts_equivalent_to_none(
        self, tmp_path: Path, capsys
    ) -> None:
        """`--yes` without `--hosts` skips both interaction and install (FR-702/703)."""
        self._link_packs(tmp_path)
        rc = main(["init", "--path", str(tmp_path), "--yes"])
        assert rc == 0
        captured = capsys.readouterr()
        # No "Installed N skills..." marker.
        assert "Installed" not in captured.out
        # No host directories.
        assert not (tmp_path / ".claude").exists()

    def test_hosts_none_explicit(self, tmp_path: Path, capsys) -> None:
        self._link_packs(tmp_path)
        rc = main(["init", "--path", str(tmp_path), "--hosts", "none"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Installed" not in captured.out
        assert not (tmp_path / ".claude").exists()

    def test_no_packs_dir_succeeds_with_marker(
        self, tmp_path: Path, capsys
    ) -> None:
        """FR-704 acceptance #3: missing packs/ dir → exit 0, no host file written."""
        # NB: we deliberately do NOT link packs into tmp_path.
        rc = main(["init", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "No packs found" in captured.out
        # An "Installed 0 skills, 0 agents..." marker still goes out per FR-709.
        assert "Installed 0 skills, 0 agents" in captured.out
        # No skill files created.
        assert not (tmp_path / ".claude/skills/garage-hello/SKILL.md").exists()

    def test_subprocess_smoke_three_hosts(self, tmp_path: Path) -> None:
        """T4 自动化 smoke fallback: run garage CLI through subprocess for full end-to-end.

        Covers the carry-forward F-5 from tasks-review (manual smoke replacement).
        """
        import subprocess
        import sys as _sys

        self._link_packs(tmp_path)
        result = subprocess.run(
            [
                _sys.executable, "-m", "garage_os.cli",
                "init", "--hosts", "all", "--path", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(self.REPO_ROOT),
            timeout=30,
        )
        assert result.returncode == 0, (
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert (tmp_path / ".claude/skills/garage-hello/SKILL.md").exists()
        assert (tmp_path / ".cursor/skills/garage-hello/SKILL.md").exists()
        assert (tmp_path / ".opencode/skills/garage-hello/SKILL.md").exists()
        # Counts are per-target-write (1 skill × 3 hosts; agents skip cursor),
        # but use regex so this test stays robust if packs/garage/ grows new
        # skills/agents in the future.
        import re as _re
        assert _re.search(
            r"Installed \d+ skills, \d+ agents into hosts:",
            result.stdout,
        ), f"marker not found in stdout: {result.stdout!r}"


class TestInitErrorPaths:
    """F007 test-review carry-forward: end-to-end CLI exit-code coverage.

    Pipeline-layer error paths are unit-tested in tests/adapter/installer/;
    these tests verify the CLI exit-code wrapping in cli._init.
    """

    @staticmethod
    def _link_packs(tmp_path: Path) -> None:
        link = tmp_path / "packs"
        if link.exists() or link.is_symlink():
            return
        link.symlink_to(TestInitWithHosts.PACKS_ROOT)

    def test_conflicting_skill_exits_2(self, tmp_path: Path, capsys) -> None:
        """Two packs with the same skill_id → exit code 2 (FR-704 acceptance #4)."""
        # Build a 2-pack fixture with the same skill_id 'foo' in both.
        for pack_id in ("packs_a", "packs_b"):
            pack_dir = tmp_path / "packs" / pack_id
            skill_dir = pack_dir / "skills" / "foo"
            skill_dir.mkdir(parents=True)
            (pack_dir / "pack.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "pack_id": pack_id,
                        "version": "0.1.0",
                        "description": "fixture",
                        "skills": ["foo"],
                        "agents": [],
                    }
                ),
                encoding="utf-8",
            )
            (skill_dir / "SKILL.md").write_text(
                "---\nname: foo\ndescription: x\n---\n\n# foo\n",
                encoding="utf-8",
            )
        rc = main(["init", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 2
        captured = capsys.readouterr()
        assert "Conflicting skill" in captured.err
        assert "packs_a" in captured.err
        assert "packs_b" in captured.err

    def test_invalid_pack_json_exits_1(self, tmp_path: Path, capsys) -> None:
        """Malformed pack.json → exit 1, .garage/ still created (CON-702)."""
        broken = tmp_path / "packs" / "broken"
        broken.mkdir(parents=True)
        (broken / "pack.json").write_text("{ broken json", encoding="utf-8")
        rc = main(["init", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Invalid pack" in captured.err
        # CON-702: .garage/ still created.
        assert (tmp_path / ".garage").is_dir()

    def test_skill_without_frontmatter_exits_1(
        self, tmp_path: Path, capsys
    ) -> None:
        """SKILL.md without front matter → MalformedFrontmatterError → exit 1."""
        pack_dir = tmp_path / "packs" / "garage"
        skill_dir = pack_dir / "skills" / "bad-skill"
        skill_dir.mkdir(parents=True)
        (pack_dir / "pack.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pack_id": "garage",
                    "version": "0.1.0",
                    "description": "x",
                    "skills": ["bad-skill"],
                    "agents": [],
                }
            ),
            encoding="utf-8",
        )
        # No '---' delimiter at all.
        (skill_dir / "SKILL.md").write_text(
            "# Bad Skill\n\nNo front matter.\n", encoding="utf-8"
        )
        rc = main(["init", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "marker injection failed" in captured.err.lower() or "front matter" in captured.err.lower()

    def test_non_tty_no_flags_writes_notice_and_exits_0(
        self, tmp_path: Path, capsys
    ) -> None:
        """FR-703: non-TTY + no --hosts/--yes → empty hosts + stderr notice + exit 0."""
        # pytest's stdin is non-TTY by default → triggers the non-interactive path.
        rc = main(["init", "--path", str(tmp_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Initialized garage-agent in" in captured.out
        assert "Installed" not in captured.out
        # Non-interactive notice on stderr.
        assert "non-interactive" in captured.err.lower()
        # No host directory created.
        assert not (tmp_path / ".claude").exists()

    def test_pack_manifest_mismatch_exits_1(self, tmp_path: Path, capsys) -> None:
        """pack.json claims skill that disk doesn't have → exit 1."""
        pack_dir = tmp_path / "packs" / "garage"
        pack_dir.mkdir(parents=True)
        (pack_dir / "pack.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "pack_id": "garage",
                    "version": "0.1.0",
                    "description": "x",
                    "skills": ["ghost"],
                    "agents": [],
                }
            ),
            encoding="utf-8",
        )
        # No skills/ghost/ on disk.
        rc = main(["init", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Pack manifest mismatch" in captured.err or "Invalid pack" in captured.err


# ===========================================================================
# F009 T4: --scope flag + per-host override + status scope 分组 测试
# ===========================================================================


class TestInitWithScope:
    """F009 FR-901/902/909: --scope flag + per-host override + stdout marker.

    fixture isolation (INV-F9-8):
    - 用 monkeypatch Path.home() 隔离, 不污染真实 ~/
    """

    REPO_ROOT = Path(__file__).resolve().parents[1]

    @staticmethod
    def _link_packs(tmp_path: Path) -> None:
        link = tmp_path / "packs"
        if link.exists() or link.is_symlink():
            return
        link.symlink_to(TestInitWithScope.REPO_ROOT / "packs")

    @staticmethod
    def _fake_home(tmp_path: Path, monkeypatch) -> Path:
        fake = tmp_path / "fake-home"
        fake.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake))
        return fake

    def test_scope_flag_default_project_F008_compat(
        self, tmp_path: Path, capsys
    ) -> None:
        """FR-901: --scope project (默认) 等价 F007/F008 行为 (CON-901)."""
        self._link_packs(tmp_path)
        rc = main(
            [
                "init",
                "--path",
                str(tmp_path),
                "--hosts",
                "claude",
                "--scope",
                "project",
            ]
        )
        assert rc == 0
        # SKILL.md 落到 cwd/.claude/skills/ (project scope)
        assert (tmp_path / ".claude/skills/garage-hello/SKILL.md").exists()

    def test_scope_user_explicit(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        """FR-901 + FR-904: --scope user 装到 ~/.claude/skills/ (fixture-isolated)."""
        fake_home = self._fake_home(tmp_path, monkeypatch)
        self._link_packs(tmp_path)

        rc = main(
            [
                "init",
                "--path",
                str(tmp_path),
                "--hosts",
                "claude",
                "--scope",
                "user",
            ]
        )
        assert rc == 0
        # SKILL.md 装到 fake_home (user scope), 不创建 cwd/.claude/
        assert (fake_home / ".claude/skills/garage-hello/SKILL.md").exists()
        assert not (tmp_path / ".claude").exists()

    def test_per_host_override_syntax(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        """FR-902: --hosts claude:user,cursor:project 正确分流."""
        fake_home = self._fake_home(tmp_path, monkeypatch)
        self._link_packs(tmp_path)

        rc = main(
            [
                "init",
                "--path",
                str(tmp_path),
                "--hosts",
                "claude:user,cursor:project",
            ]
        )
        assert rc == 0
        # claude → fake_home/.claude/skills/
        assert (fake_home / ".claude/skills/garage-hello/SKILL.md").exists()
        # cursor → cwd/.cursor/skills/
        assert (tmp_path / ".cursor/skills/garage-hello/SKILL.md").exists()
        # 反向: claude 不在 cwd, cursor 不在 fake_home
        assert not (tmp_path / ".claude").exists()
        assert not (fake_home / ".cursor").exists()

    def test_unknown_scope_argparse_rejected(self, tmp_path: Path, capsys) -> None:
        """FR-901 验收 #4: --scope unknown 被 argparse choices 拒绝 (SystemExit 2).

        实施差异说明: spec FR-901 验收 #4 写 'exit 1 + stderr Unknown scope: unknown',
        但实施时把 --scope 用 argparse choices=['project', 'user'] 在 parse 阶段拒绝,
        argparse 默认 SystemExit(2) + 自己的 stderr 错误消息. 这是更早期 + 更严格的
        拒绝, 与 spec 验收语义一致 (拒绝 invalid scope), 仅退出码差异 (2 vs 1) —
        argparse choices 是 Python 标准做法, 与 F007 既有 --hosts 没用 choices
        (因为支持 'all'/'none'/comma-list) 不同; --scope 取值集合固定可用 choices.
        """
        self._link_packs(tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "init",
                    "--path",
                    str(tmp_path),
                    "--hosts",
                    "claude",
                    "--scope",
                    "unknown",
                ]
            )
        assert exc_info.value.code == 2  # argparse choices rejection

    def test_per_host_override_unknown_scope_exits_1(
        self, tmp_path: Path, capsys
    ) -> None:
        """FR-902 验收 #3: --hosts claude:bad → exit 1 + stderr."""
        self._link_packs(tmp_path)
        rc = main(
            [
                "init",
                "--path",
                str(tmp_path),
                "--hosts",
                "claude:bad",
            ]
        )
        assert rc == 1
        captured = capsys.readouterr()
        assert "Unknown scope: bad" in captured.err

    def test_stdout_marker_F007_grep_compat(
        self, tmp_path: Path, capsys
    ) -> None:
        """FR-909: F007 既有 stdout marker 字面不变, grep 仍命中.

        ``grep -cE '^Installed [0-9]+ skills, [0-9]+ agents into hosts:'`` 命中 == 1
        """
        self._link_packs(tmp_path)
        rc = main(["init", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 0
        captured = capsys.readouterr()
        # F007 grep pattern 仍命中
        import re

        matches = re.findall(
            r"^Installed [0-9]+ skills, [0-9]+ agents into hosts:",
            captured.out,
            re.MULTILINE,
        )
        assert len(matches) == 1, (
            f"F007 grep pattern 命中数 = {len(matches)}, 期望 1; stdout: {captured.out!r}"
        )

    def test_stdout_marker_mixed_scope_extra_line(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        """FR-909: 多 scope 时另起一行附加 scope 分布段; F007 marker 行不变."""
        self._fake_home(tmp_path, monkeypatch)
        self._link_packs(tmp_path)

        rc = main(
            [
                "init",
                "--path",
                str(tmp_path),
                "--hosts",
                "claude:user,cursor:project",
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        # F007 marker 行仍恰好 1 次
        import re

        matches = re.findall(
            r"^Installed [0-9]+ skills, [0-9]+ agents into hosts:",
            captured.out,
            re.MULTILINE,
        )
        assert len(matches) == 1
        # 多 scope 时, 附加段独立一行 (含 'user-scope' + 'project-scope')
        assert "user-scope" in captured.out
        assert "project-scope" in captured.out


class TestStatusScopeGrouped:
    """F009 FR-908 + ADR-D9-7: garage status 按 scope 分组 (nested bullets)."""

    REPO_ROOT = Path(__file__).resolve().parents[1]

    @staticmethod
    def _link_packs(tmp_path: Path) -> None:
        link = tmp_path / "packs"
        if link.exists() or link.is_symlink():
            return
        link.symlink_to(TestStatusScopeGrouped.REPO_ROOT / "packs")

    def test_status_no_manifest_no_scope_segment(
        self, tmp_path: Path, capsys
    ) -> None:
        """F008 兼容: 无 manifest 时 status 不打印 scope 分组段."""
        # 仅 init 不带 hosts → 无 manifest
        main(["init", "--path", str(tmp_path), "--yes"])
        # 加一些数据让 status 不 'No data'
        knowledge_dir = tmp_path / ".garage" / "knowledge" / "decisions"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        (knowledge_dir / "test.md").write_text("# test\n", encoding="utf-8")
        capsys.readouterr()  # clear

        main(["status", "--path", str(tmp_path)])
        captured = capsys.readouterr()
        # status 不应含 scope 分组段
        assert "Installed packs" not in captured.out

    def test_status_project_scope_only(
        self, tmp_path: Path, capsys
    ) -> None:
        """status 在 project scope only manifest 时只打 project 段."""
        self._link_packs(tmp_path)
        rc = main(
            [
                "init",
                "--path",
                str(tmp_path),
                "--hosts",
                "claude",
                "--scope",
                "project",
            ]
        )
        assert rc == 0
        # 加一些数据让 status 不 'No data'
        knowledge_dir = tmp_path / ".garage" / "knowledge" / "decisions"
        knowledge_dir.mkdir(parents=True, exist_ok=True)
        (knowledge_dir / "t.md").write_text("# t\n", encoding="utf-8")
        capsys.readouterr()

        main(["status", "--path", str(tmp_path)])
        captured = capsys.readouterr()
        assert "Installed packs (project scope):" in captured.out
        assert "Installed packs (user scope):" not in captured.out
        assert "claude:" in captured.out


# ===========================================================================
# F010 T4: garage sync CLI + status sync segment tests
# ===========================================================================


class TestSyncCommand:
    """F010 FR-1001/2/8 + ADR-D10-12/13: garage sync CLI."""

    @staticmethod
    def _seed_decision(workspace_root: Path) -> None:
        from datetime import datetime as _dt
        from garage_os.knowledge.knowledge_store import KnowledgeStore
        from garage_os.storage.file_storage import FileStorage
        from garage_os.types import KnowledgeEntry, KnowledgeType
        storage = FileStorage(workspace_root / ".garage")
        KnowledgeStore(storage).store(
            KnowledgeEntry(
                id="d-001",
                type=KnowledgeType.DECISION,
                topic="test",
                date=_dt(2026, 4, 24),
                tags=[],
                content="content",
            )
        )

    @staticmethod
    def _fake_home(tmp_path: Path, monkeypatch) -> Path:
        fake = tmp_path / "fake-home"
        fake.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake))
        return fake

    def test_sync_hosts_claude_project_default(self, tmp_path: Path, capsys) -> None:
        self._seed_decision(tmp_path)
        rc = main(["sync", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 0
        # CLAUDE.md created in cwd
        assert (tmp_path / "CLAUDE.md").exists()
        # sync-manifest.json created
        assert (tmp_path / ".garage/config/sync-manifest.json").exists()

    def test_sync_hosts_claude_scope_user(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        fake_home = self._fake_home(tmp_path, monkeypatch)
        self._seed_decision(tmp_path)
        rc = main(
            ["sync", "--path", str(tmp_path), "--hosts", "claude", "--scope", "user"]
        )
        assert rc == 0
        assert (fake_home / ".claude/CLAUDE.md").exists()
        assert not (tmp_path / "CLAUDE.md").exists()

    def test_sync_per_host_override(
        self, tmp_path: Path, capsys, monkeypatch
    ) -> None:
        fake_home = self._fake_home(tmp_path, monkeypatch)
        self._seed_decision(tmp_path)
        rc = main(
            ["sync", "--path", str(tmp_path), "--hosts", "claude:user,cursor:project"]
        )
        assert rc == 0
        assert (fake_home / ".claude/CLAUDE.md").exists()
        assert (tmp_path / ".cursor/rules/garage-context.mdc").exists()

    def test_sync_force_overrides_skip(self, tmp_path: Path, capsys) -> None:
        self._seed_decision(tmp_path)
        # First sync
        main(["sync", "--path", str(tmp_path), "--hosts", "claude"])
        # User modifies marker block
        claude_md = tmp_path / "CLAUDE.md"
        edited = claude_md.read_text().replace("test", "USER_EDITED")
        claude_md.write_text(edited)
        # Second sync with --force overrides
        rc = main(["sync", "--path", str(tmp_path), "--hosts", "claude", "--force"])
        assert rc == 0
        assert "USER_EDITED" not in claude_md.read_text()

    def test_sync_stdout_marker_grep_compat(self, tmp_path: Path, capsys) -> None:
        """FR-1008: stdout marker `Synced N knowledge entries + M experience records into hosts:`."""
        self._seed_decision(tmp_path)
        rc = main(["sync", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 0
        captured = capsys.readouterr()
        import re
        matches = re.findall(
            r"^Synced [0-9]+ knowledge entries \+ [0-9]+ experience records into hosts:",
            captured.out,
            re.MULTILINE,
        )
        assert len(matches) == 1, (
            f"FR-1008 marker grep hit count = {len(matches)}, expected 1; stdout: {captured.out!r}"
        )

    def test_sync_no_knowledge_no_section(self, tmp_path: Path, capsys) -> None:
        """Empty .garage/knowledge/ → sync still OK with 'No Garage knowledge yet' message."""
        rc = main(["sync", "--path", str(tmp_path), "--hosts", "claude"])
        assert rc == 0
        assert (tmp_path / "CLAUDE.md").exists()
        assert "No Garage knowledge or experience yet" in (tmp_path / "CLAUDE.md").read_text()

    def test_sync_unknown_scope_via_per_host_exits_1(self, tmp_path: Path, capsys) -> None:
        rc = main(["sync", "--path", str(tmp_path), "--hosts", "claude:bad"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Unknown scope: bad" in captured.err


class TestStatusSyncSegment:
    """F010 FR-1009 + ADR-D10-12 + CON-1001: status sync segment."""

    def _seed_and_init(self, tmp_path: Path) -> None:
        # Init garage to satisfy _status pre-check
        main(["init", "--path", str(tmp_path), "--yes"])

    def test_status_no_sync_manifest_no_segment(self, tmp_path: Path, capsys) -> None:
        """CON-1001 fallback: sync-manifest.json absent → no sync-related output line."""
        self._seed_and_init(tmp_path)
        # Add some knowledge to ensure status doesn't return 'No data'
        from garage_os.storage.file_storage import FileStorage
        FileStorage(tmp_path / ".garage").write_text(
            "knowledge/decisions/test.md", "---\nid: x\n---\n# x\n"
        )
        capsys.readouterr()  # clear
        main(["status", "--path", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Last synced" not in out

    def test_status_with_sync_manifest_shows_segment(
        self, tmp_path: Path, capsys
    ) -> None:
        from datetime import datetime as _dt
        from garage_os.knowledge.knowledge_store import KnowledgeStore
        from garage_os.storage.file_storage import FileStorage
        from garage_os.types import KnowledgeEntry, KnowledgeType

        self._seed_and_init(tmp_path)
        storage = FileStorage(tmp_path / ".garage")
        KnowledgeStore(storage).store(
            KnowledgeEntry(
                id="d-001",
                type=KnowledgeType.DECISION,
                topic="test",
                date=_dt(2026, 4, 24),
                tags=[],
                content="c",
            )
        )
        # Sync to create sync-manifest.json
        main(["sync", "--path", str(tmp_path), "--hosts", "claude"])
        capsys.readouterr()

        # Status should now include sync segment
        main(["status", "--path", str(tmp_path)])
        out = capsys.readouterr().out
        assert "Last synced (per host):" in out
        assert "claude" in out


# ===========================================================================
# F010 T6: garage session import CLI tests
# ===========================================================================


class TestSessionImportCommand:
    """F010 FR-1005/1006: garage session import CLI."""

    FIXTURE_DIR = Path(__file__).resolve().parent / "ingest" / "fixtures"

    @staticmethod
    def _patch_claude_history(monkeypatch, fixture_dir: Path) -> None:
        from garage_os.ingest.host_readers import claude_code as cc
        original_init = cc.ClaudeCodeHistoryReader.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["history_dir"] = fixture_dir
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(cc.ClaudeCodeHistoryReader, "__init__", patched_init)

    def test_import_all_from_claude_code(self, tmp_path: Path, capsys, monkeypatch) -> None:
        # Init garage skeleton (so _find_garage_root works)
        main(["init", "--path", str(tmp_path), "--yes"])
        capsys.readouterr()

        # Patch Claude reader to use fixture dir
        self._patch_claude_history(monkeypatch, self.FIXTURE_DIR / "claude_code")

        rc = main([
            "session", "import",
            "--path", str(tmp_path),
            "--from", "claude-code",
            "--all",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Imported" in captured.out
        # FR-1005 negative path: broken JSON fixture skipped at list_conversations
        # (reader emits stderr "Skipped unreadable conversation"), so summary.skipped=0
        # but stderr captures the skip notice.
        assert "Skipped unreadable" in captured.err
        assert "conversation-002-broken" in captured.err

    def test_import_alias_claude(self, tmp_path: Path, capsys, monkeypatch) -> None:
        """Alias 'claude' → 'claude-code' resolution."""
        main(["init", "--path", str(tmp_path), "--yes"])
        capsys.readouterr()
        self._patch_claude_history(monkeypatch, self.FIXTURE_DIR / "claude_code")

        rc = main([
            "session", "import",
            "--path", str(tmp_path),
            "--from", "claude",
            "--all",
        ])
        assert rc == 0
        # imported as canonical "claude-code"
        captured = capsys.readouterr()
        assert "claude-code" in captured.out

    def test_import_cursor_deferred_exits_1(self, tmp_path: Path, capsys) -> None:
        """ADR-D10-10: cursor stub raises NotImplementedError → exit 1."""
        main(["init", "--path", str(tmp_path), "--yes"])
        capsys.readouterr()

        rc = main([
            "session", "import",
            "--path", str(tmp_path),
            "--from", "cursor",
            "--all",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "deferred" in captured.err.lower() or "not yet implemented" in captured.err.lower()
        assert "D-1010" in captured.err

    def test_import_unknown_host_exits_1(self, tmp_path: Path, capsys) -> None:
        main(["init", "--path", str(tmp_path), "--yes"])
        capsys.readouterr()

        rc = main([
            "session", "import",
            "--path", str(tmp_path),
            "--from", "nonexistent",
            "--all",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Unknown host" in captured.err

    def test_import_non_tty_without_all_returns_0(self, tmp_path: Path, capsys, monkeypatch) -> None:
        """FR-1006 + ADR-D10-9 r2: non-TTY without --all → exit 0 + stderr notice."""
        main(["init", "--path", str(tmp_path), "--yes"])
        capsys.readouterr()
        self._patch_claude_history(monkeypatch, self.FIXTURE_DIR / "claude_code")

        rc = main([
            "session", "import",
            "--path", str(tmp_path),
            "--from", "claude-code",
        ])
        assert rc == 0
        # No conversations imported (selector returned []), no stdout marker
        captured = capsys.readouterr()
        assert "non-interactive shell detected" in captured.err


# ===========================================================================
# F011 T4: garage pack install + ls CLI tests
# ===========================================================================


class TestPackInstallCommand:
    """F011 FR-1106 + ADR-D11-4..7."""

    @staticmethod
    def _build_test_pack(repo_dir: Path, pack_id: str = "test-pack") -> None:
        import json
        import subprocess
        (repo_dir / "skills" / "hello-skill").mkdir(parents=True)
        (repo_dir / "skills" / "hello-skill" / "SKILL.md").write_text(
            "---\nname: hello-skill\ndescription: minimal\n---\n# Hello\n",
            encoding="utf-8",
        )
        (repo_dir / "pack.json").write_text(
            json.dumps({
                "schema_version": 1,
                "pack_id": pack_id,
                "version": "0.1.0",
                "description": "F011 CLI test",
                "skills": ["hello-skill"],
                "agents": [],
            }, indent=2),
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=repo_dir, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=T", "commit", "-q", "-m", "init"],
            cwd=repo_dir,
            check=True,
        )

    def test_install_local_pack_via_cli(self, tmp_path: Path, capsys) -> None:
        repo_dir = tmp_path / "src-pack"
        repo_dir.mkdir()
        self._build_test_pack(repo_dir, pack_id="cli-test-pack")

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        url = f"file://{repo_dir}"
        rc = main(["pack", "install", "--path", str(workspace), url])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Installed pack 'cli-test-pack'" in captured.out
        assert "v0.1.0" in captured.out

    def test_install_invalid_url_exits_1(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        rc = main([
            "pack", "install",
            "--path", str(workspace),
            "https://nonexistent-host-12345.invalid/repo.git",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "Pack install failed" in captured.err


class TestPackLsCommand:
    """F011 FR-1107 + ADR-D11-7."""

    def test_ls_empty_workspace(self, tmp_path: Path, capsys) -> None:
        rc = main(["pack", "ls", "--path", str(tmp_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Installed packs (0 total):" in captured.out

    def test_ls_workspace_packs(self, tmp_path: Path, capsys) -> None:
        # Use real workspace with 5 packs (code-audit added in Slice A)
        REPO_ROOT = Path(__file__).resolve().parents[1]
        rc = main(["pack", "ls", "--path", str(REPO_ROOT)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Installed packs (5 total):" in captured.out
        # All 5 packs listed alphabetically
        for pack_id in ["code-audit", "coding", "garage", "search", "writing"]:
            assert pack_id in captured.out
        # All show '[local]' since no source_url
        assert "[local]" in captured.out


# ===========================================================================
# F012-A T1: garage pack uninstall CLI tests
# ===========================================================================


class TestPackUninstallCommand:
    """F012-A FR-1201..1203 + ADR-D12-2."""

    @staticmethod
    def _build_and_install(workspace: Path, repo: Path, pack_id: str = "cli-uninstall-test") -> None:
        import json
        import subprocess
        from garage_os.adapter.installer.pack_install import install_pack_from_url
        from garage_os.adapter.installer.pipeline import install_packs

        (repo / "skills" / "h").mkdir(parents=True)
        (repo / "skills" / "h" / "SKILL.md").write_text(
            "---\nname: h\ndescription: minimal\n---\n# H\n", encoding="utf-8",
        )
        (repo / "pack.json").write_text(json.dumps({
            "schema_version": 1, "pack_id": pack_id, "version": "0.1.0",
            "description": "x", "skills": ["h"], "agents": [],
        }), encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=T", "commit", "-q", "-m", "init"],
            cwd=repo, check=True,
        )
        install_pack_from_url(workspace, f"file://{repo}")
        install_packs(workspace, packs_root=workspace / "packs", hosts=["claude"])

    def test_uninstall_yes_via_cli(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        repo = tmp_path / "src"
        repo.mkdir()
        self._build_and_install(workspace, repo, "cli-test")

        rc = main(["pack", "uninstall", "--path", str(workspace), "cli-test", "--yes"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Uninstalled pack 'cli-test'" in captured.out
        assert not (workspace / "packs" / "cli-test").exists()

    def test_uninstall_dry_run_via_cli(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        repo = tmp_path / "src"
        repo.mkdir()
        self._build_and_install(workspace, repo, "dry-cli-test")

        rc = main(["pack", "uninstall", "--path", str(workspace), "dry-cli-test", "--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out
        assert (workspace / "packs" / "dry-cli-test").exists()

    def test_uninstall_nonexistent_exits_1(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        rc = main(["pack", "uninstall", "--path", str(workspace), "nonexistent", "--yes"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "uninstall failed" in captured.err.lower()


# ===========================================================================
# F012-B T2: garage pack update CLI tests
# ===========================================================================


class TestPackUpdateCommand:
    """F012-B FR-1204..1206 + ADR-D12-3 r2."""

    @staticmethod
    def _build_pack(repo: Path, pack_id: str, version: str) -> str:
        import json, subprocess
        (repo / "skills" / "h").mkdir(parents=True, exist_ok=True)
        (repo / "skills" / "h" / "SKILL.md").write_text(
            f"---\nname: h\ndescription: v{version}\n---\n# v{version}\n", encoding="utf-8",
        )
        (repo / "pack.json").write_text(json.dumps({
            "schema_version": 1, "pack_id": pack_id, "version": version,
            "description": f"v{version}", "skills": ["h"], "agents": [],
        }), encoding="utf-8")
        if not (repo / ".git").exists():
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=T", "commit", "-q",
             "--allow-empty", "-m", f"v{version}"],
            cwd=repo, check=True,
        )
        return f"file://{repo}"

    def test_update_yes_via_cli(self, tmp_path: Path, capsys) -> None:
        from garage_os.adapter.installer.pack_install import install_pack_from_url
        workspace = tmp_path / "ws"
        workspace.mkdir()
        repo = tmp_path / "src"
        repo.mkdir()
        url = self._build_pack(repo, "cli-update-test", "0.1.0")
        install_pack_from_url(workspace, url)
        # Bump remote
        self._build_pack(repo, "cli-update-test", "0.2.0")

        rc = main(["pack", "update", "--path", str(workspace), "cli-update-test", "--yes"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Updated pack 'cli-update-test'" in captured.out
        assert "v0.1.0 to v0.2.0" in captured.out

    def test_update_already_up_to_date(self, tmp_path: Path, capsys) -> None:
        from garage_os.adapter.installer.pack_install import install_pack_from_url
        workspace = tmp_path / "ws"
        workspace.mkdir()
        repo = tmp_path / "src"
        repo.mkdir()
        url = self._build_pack(repo, "utd-test", "0.1.0")
        install_pack_from_url(workspace, url)

        rc = main(["pack", "update", "--path", str(workspace), "utd-test", "--yes"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "already up to date" in captured.out.lower()

    def test_update_nonexistent_exits_1(self, tmp_path: Path, capsys) -> None:
        rc = main(["pack", "update", "--path", str(tmp_path), "nonexistent", "--yes"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "update failed" in captured.err.lower()


# ===========================================================================
# F012-C T3: garage pack publish CLI tests
# ===========================================================================


class TestPackPublishCommand:
    """F012-C FR-1207..1210 + ADR-D12-4 r2."""

    @staticmethod
    def _build_pack(workspace: Path, pack_id: str, with_sensitive: bool = False) -> None:
        import json
        pack_dir = workspace / "packs" / pack_id
        pack_dir.mkdir(parents=True)
        (pack_dir / "skills" / "h").mkdir(parents=True)
        (pack_dir / "skills" / "h" / "SKILL.md").write_text(
            "---\nname: h\ndescription: x\n---\n# H\n", encoding="utf-8",
        )
        if with_sensitive:
            (pack_dir / "config.env").write_text("password=foo\n", encoding="utf-8")
        (pack_dir / "pack.json").write_text(json.dumps({
            "schema_version": 1, "pack_id": pack_id, "version": "0.1.0",
            "description": "x", "skills": ["h"], "agents": [],
        }), encoding="utf-8")

    @staticmethod
    def _bare_remote(tmp_path: Path) -> str:
        import subprocess
        bare = tmp_path / "bare.git"
        subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
        return f"file://{bare}"

    def test_publish_yes_via_cli(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        self._build_pack(workspace, "cli-pub-test")
        url = self._bare_remote(tmp_path)

        rc = main([
            "pack", "publish", "--path", str(workspace), "cli-pub-test",
            "--to", url, "--yes",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Published pack 'cli-pub-test'" in captured.out

    def test_publish_sensitive_aborts(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        self._build_pack(workspace, "cli-sens-test", with_sensitive=True)
        url = self._bare_remote(tmp_path)

        rc = main([
            "pack", "publish", "--path", str(workspace), "cli-sens-test",
            "--to", url, "--yes",
        ])
        assert rc == 1  # sensitive abort
        captured = capsys.readouterr()
        assert "Sensitive content detected" in captured.err

    def test_publish_force_bypasses_sensitive(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        self._build_pack(workspace, "cli-fp-test", with_sensitive=True)
        url = self._bare_remote(tmp_path)

        rc = main([
            "pack", "publish", "--path", str(workspace), "cli-fp-test",
            "--to", url, "--yes", "--force",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Published pack" in captured.out

    def test_publish_dry_run(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        self._build_pack(workspace, "cli-dr-test")
        url = self._bare_remote(tmp_path)

        rc = main([
            "pack", "publish", "--path", str(workspace), "cli-dr-test",
            "--to", url, "--dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out


# ===========================================================================
# F012-D T4: garage knowledge export --anonymize CLI tests
# ===========================================================================


class TestKnowledgeExportCommand:
    """F012-D FR-1211..1213 + ADR-D12-5 r2."""

    @staticmethod
    def _seed(workspace: Path) -> None:
        from datetime import datetime
        from garage_os.knowledge.knowledge_store import KnowledgeStore
        from garage_os.storage.file_storage import FileStorage
        from garage_os.types import KnowledgeEntry, KnowledgeType
        storage = FileStorage(workspace / ".garage")
        KnowledgeStore(storage).store(KnowledgeEntry(
            id="cli-001", type=KnowledgeType.DECISION, topic="t",
            date=datetime(2026, 4, 25), tags=[],
            content="email: alice@example.com api_key=sk-test123",
        ))

    def test_export_anonymize_via_cli(self, tmp_path: Path, capsys, monkeypatch) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        # Init garage
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace)

        # Redirect HOME
        fake_home = tmp_path / "fake-home"
        fake_home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        rc = main([
            "knowledge", "export", "--path", str(workspace), "--anonymize",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Exported 1 entries" in captured.out
        assert "redacted" in captured.out
        # Tarball exists in fake_home
        exports_dir = fake_home / ".garage" / "exports"
        tarballs = list(exports_dir.glob("*.tar.gz"))
        assert len(tarballs) == 1

    def test_export_dry_run_via_cli(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace)

        rc = main([
            "knowledge", "export", "--path", str(workspace),
            "--anonymize", "--dry-run",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.err

    def test_export_without_anonymize_flag_argparse_required(
        self, tmp_path: Path, capsys
    ) -> None:
        """--anonymize is argparse-required (FR-1211 only mode in F012)."""
        with pytest.raises(SystemExit) as exc_info:
            main(["knowledge", "export", "--path", str(tmp_path)])
        assert exc_info.value.code != 0  # argparse rejects missing required arg

    def test_export_custom_output_in_workspace_warns(
        self, tmp_path: Path, capsys
    ) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace)

        output = workspace / "myexports"
        rc = main([
            "knowledge", "export", "--path", str(workspace),
            "--anonymize", "--output", str(output),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


# ===========================================================================
# F013-A T4: garage skill suggest CLI tests
# ===========================================================================


class TestSkillSuggestCommand:
    """F013-A FR-1302."""

    @staticmethod
    def _seed_records(workspace: Path, n: int = 5) -> None:
        from garage_os.knowledge.experience_index import ExperienceIndex
        from garage_os.storage.file_storage import FileStorage
        from garage_os.types import ExperienceRecord
        storage = FileStorage(workspace / ".garage")
        ei = ExperienceIndex(storage)
        for i in range(n):
            ei.store(ExperienceRecord(
                record_id=f"r-{i:03d}",
                task_type="review",
                skill_ids=[],
                tech_stack=[],
                domain="dev",
                problem_domain="review-verdict",
                outcome="success",
                duration_seconds=60,
                complexity="low",
                session_id=f"ses-{i:03d}",
                key_patterns=["verdict-format", "5-section"],
            ))

    def test_skill_suggest_empty_friendly_msg(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()

        rc = main(["skill", "suggest", "--path", str(workspace)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "No skill suggestions yet" in captured.out

    def test_skill_suggest_rescan_writes_proposals(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed_records(workspace)

        rc = main(["skill", "suggest", "--path", str(workspace), "--rescan"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Rescan complete" in captured.out
        assert "1 new proposals" in captured.out

    def test_skill_suggest_lists_proposed(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed_records(workspace)
        # First rescan
        main(["skill", "suggest", "--path", str(workspace), "--rescan"])
        capsys.readouterr()

        # Then list
        rc = main(["skill", "suggest", "--path", str(workspace)])
        assert rc == 0
        captured = capsys.readouterr()
        # Header table
        assert "ID" in captured.out
        assert "NAME" in captured.out
        assert "SCORE" in captured.out

    def test_skill_suggest_id_shows_detail_with_preview(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed_records(workspace)
        main(["skill", "suggest", "--path", str(workspace), "--rescan"])
        capsys.readouterr()

        # Find suggestion id from suggestion store
        from garage_os.skill_mining.suggestion_store import SuggestionStore
        from garage_os.skill_mining.types import SkillSuggestionStatus
        ss = SuggestionStore(workspace / ".garage")
        suggestions = ss.list_by_status(SkillSuggestionStatus.PROPOSED)
        assert len(suggestions) == 1
        sg_id = suggestions[0].id

        rc = main(["skill", "suggest", "--path", str(workspace), "--id", sg_id])
        assert rc == 0
        captured = capsys.readouterr()
        assert "SKILL.md preview" in captured.out
        assert "## When to Use" in captured.out

    def test_skill_suggest_id_not_found(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()

        rc = main(["skill", "suggest", "--path", str(workspace), "--id", "sg-nonexistent"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err

    def test_skill_suggest_status_filter(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed_records(workspace)
        main(["skill", "suggest", "--path", str(workspace), "--rescan"])
        capsys.readouterr()

        # status=promoted should be empty
        rc = main([
            "skill", "suggest", "--path", str(workspace),
            "--status", "promoted",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "No skill suggestions yet (status=promoted)" in captured.out


# ===========================================================================
# F013-A T5: garage skill promote CLI tests
# ===========================================================================


class TestSkillPromoteCommand:
    """F013-A FR-1304 + INV-F13-1 + INV-F13-2 + CON-1304."""

    @staticmethod
    def _seed_and_propose(workspace: Path) -> str:
        from garage_os.knowledge.experience_index import ExperienceIndex
        from garage_os.skill_mining.suggestion_store import SuggestionStore
        from garage_os.skill_mining.types import SkillSuggestionStatus
        from garage_os.storage.file_storage import FileStorage
        from garage_os.types import ExperienceRecord
        storage = FileStorage(workspace / ".garage")
        ei = ExperienceIndex(storage)
        for i in range(5):
            ei.store(ExperienceRecord(
                record_id=f"r-{i:03d}",
                task_type="review",
                skill_ids=[],
                tech_stack=[],
                domain="dev",
                problem_domain="review-verdict",
                outcome="success",
                duration_seconds=60,
                complexity="low",
                session_id=f"ses-{i:03d}",
                key_patterns=["verdict-format", "5-section"],
                lessons_learned=[f"lesson {i}"],
            ))
        # Trigger via rescan
        main(["skill", "suggest", "--path", str(workspace), "--rescan"])
        ss = SuggestionStore(workspace / ".garage")
        return ss.list_by_status(SkillSuggestionStatus.PROPOSED)[0].id

    def test_promote_yes_writes_skill_md(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        # Need packs/garage/ to exist for target validation
        (workspace / "packs" / "garage").mkdir(parents=True)
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        sg_id = self._seed_and_propose(workspace)
        capsys.readouterr()

        rc = main(["skill", "promote", "--path", str(workspace), sg_id, "--yes"])
        assert rc == 0
        captured = capsys.readouterr()

        # SKILL.md exists in the suggestion's name dir
        from garage_os.skill_mining.suggestion_store import SuggestionStore
        from garage_os.skill_mining.types import SkillSuggestionStatus
        ss = SuggestionStore(workspace / ".garage")
        # status moved to promoted
        promoted = ss.list_by_status(SkillSuggestionStatus.PROMOTED)
        assert len(promoted) == 1
        skill_md = workspace / "packs" / "garage" / "skills" / promoted[0].suggested_name / "SKILL.md"
        assert skill_md.is_file()
        # Echo line per FR-1304
        assert "Created skill at" in captured.out
        assert "garage run" in captured.out

    def test_promote_dry_run_no_write(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "packs" / "garage").mkdir(parents=True)
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        sg_id = self._seed_and_propose(workspace)
        capsys.readouterr()

        rc = main(["skill", "promote", "--path", str(workspace), sg_id, "--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "DRY RUN" in captured.out

        # Status still proposed
        from garage_os.skill_mining.suggestion_store import SuggestionStore
        from garage_os.skill_mining.types import SkillSuggestionStatus
        ss = SuggestionStore(workspace / ".garage")
        assert len(ss.list_by_status(SkillSuggestionStatus.PROPOSED)) == 1

    def test_promote_reject_with_reason(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "packs" / "garage").mkdir(parents=True)
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        sg_id = self._seed_and_propose(workspace)
        capsys.readouterr()

        rc = main(["skill", "promote", "--path", str(workspace), sg_id, "--reject", "--yes"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Rejected" in captured.out

        from garage_os.skill_mining.suggestion_store import SuggestionStore
        from garage_os.skill_mining.types import SkillSuggestionStatus
        ss = SuggestionStore(workspace / ".garage")
        assert len(ss.list_by_status(SkillSuggestionStatus.REJECTED)) == 1

    def test_promote_target_pack_override(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "packs" / "coding").mkdir(parents=True)
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        sg_id = self._seed_and_propose(workspace)
        capsys.readouterr()

        rc = main([
            "skill", "promote", "--path", str(workspace), sg_id,
            "--yes", "--target-pack", "coding",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # Skill went to coding/, not garage/
        from garage_os.skill_mining.suggestion_store import SuggestionStore
        from garage_os.skill_mining.types import SkillSuggestionStatus
        ss = SuggestionStore(workspace / ".garage")
        promoted = ss.list_by_status(SkillSuggestionStatus.PROMOTED)
        skill_md = workspace / "packs" / "coding" / "skills" / promoted[0].suggested_name / "SKILL.md"
        assert skill_md.is_file()

    def test_promote_nonexistent_target_pack(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "packs" / "garage").mkdir(parents=True)
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        sg_id = self._seed_and_propose(workspace)
        capsys.readouterr()

        rc = main([
            "skill", "promote", "--path", str(workspace), sg_id,
            "--yes", "--target-pack", "nonexistent-pack",
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not installed" in captured.err


# ===========================================================================
# F014 T4: garage recall workflow CLI tests
# ===========================================================================


class TestRecallWorkflowCommand:
    """F014 FR-1402 + Im-4 r2 sub-sequence + CON-1405."""

    @staticmethod
    def _seed(workspace: Path, n: int = 5) -> None:
        from garage_os.knowledge.experience_index import ExperienceIndex
        from garage_os.storage.file_storage import FileStorage
        from garage_os.types import ExperienceRecord
        storage = FileStorage(workspace / ".garage")
        ei = ExperienceIndex(storage)
        for i in range(n):
            ei.store(ExperienceRecord(
                record_id=f"r-{i:03d}",
                task_type="implement",
                skill_ids=["hf-specify", "hf-design", "hf-tasks", "hf-test-driven-dev"],
                tech_stack=["python"],
                domain="dev",
                problem_domain="cli-design",
                outcome="success",
                duration_seconds=3600 + i * 100,
                complexity="medium",
                session_id=f"ses-{i:03d}",
                lessons_learned=["先 read spec 再 design"],
            ))

    def test_no_filter_errors(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()

        rc = main(["recall", "workflow", "--path", str(workspace)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "at least one of" in captured.err

    def test_problem_domain_filter(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace, n=5)

        rc = main([
            "recall", "workflow", "--path", str(workspace),
            "--problem-domain", "cli-design",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "SEQUENCE" in captured.out
        assert "hf-specify" in captured.out
        assert "5" in captured.out  # 5 hits

    def test_task_type_filter(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace, n=3)

        rc = main([
            "recall", "workflow", "--path", str(workspace),
            "--task-type", "implement",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "hf-specify" in captured.out

    def test_skill_id_filter_subsequence(self, tmp_path: Path, capsys) -> None:
        """Im-4 r2: --skill-id Z 取 Z 后子序列."""
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace, n=3)

        rc = main([
            "recall", "workflow", "--path", str(workspace),
            "--skill-id", "hf-design",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # After hf-design subseq is "hf-tasks → hf-test-driven-dev"
        assert "hf-tasks" in captured.out
        assert "hf-test-driven-dev" in captured.out
        # hf-specify and hf-design should NOT appear in the sequence column
        # (they're before the cut)
        assert "hf-specify" not in captured.out

    def test_top_k_override(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        # Seed 4 distinct sequences
        from garage_os.knowledge.experience_index import ExperienceIndex
        from garage_os.storage.file_storage import FileStorage
        from garage_os.types import ExperienceRecord
        storage = FileStorage(workspace / ".garage")
        ei = ExperienceIndex(storage)
        for j in range(4):
            for i in range(3):
                ei.store(ExperienceRecord(
                    record_id=f"r-{j}-{i}",
                    task_type="implement",
                    skill_ids=[f"skill-{j}", "hf-tasks"],
                    tech_stack=[],
                    domain="d",
                    problem_domain="cli-design",
                    outcome="success",
                    duration_seconds=60,
                    complexity="low",
                    session_id=f"ses-{j}-{i}",
                ))

        rc = main([
            "recall", "workflow", "--path", str(workspace),
            "--problem-domain", "cli-design",
            "--top-k", "2",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        # Only 2 of 4 sequences shown
        sequence_lines = [l for l in captured.out.splitlines() if "skill-" in l]
        assert len(sequence_lines) == 2

    def test_json_output_schema(self, tmp_path: Path, capsys) -> None:
        import json
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace, n=5)

        rc = main([
            "recall", "workflow", "--path", str(workspace),
            "--problem-domain", "cli-design",
            "--json",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert "advisories" in payload
        assert "scanned_count" in payload
        assert "bucket_size" in payload
        assert "threshold_met" in payload
        assert payload["threshold_met"] is True
        assert payload["bucket_size"] == 5
        assert len(payload["advisories"]) == 1
        adv = payload["advisories"][0]
        assert adv["skills"] == ["hf-specify", "hf-design", "hf-tasks", "hf-test-driven-dev"]
        assert adv["count"] == 5

    def test_below_threshold_friendly_msg(self, tmp_path: Path, capsys) -> None:
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace, n=2)  # below threshold 3

        rc = main([
            "recall", "workflow", "--path", str(workspace),
            "--problem-domain", "cli-design",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "No workflow advisory yet" in captured.out
        assert "current N for bucket: 2" in captured.out

    def test_rebuild_cache_flag(self, tmp_path: Path, capsys) -> None:
        from garage_os.workflow_recall.cache import WorkflowRecallCache
        workspace = tmp_path / "ws"
        workspace.mkdir()
        main(["init", "--path", str(workspace), "--yes"])
        capsys.readouterr()
        self._seed(workspace, n=5)

        cache = WorkflowRecallCache(workspace / ".garage")
        cache.write_last_indexed(scanned_count=999)  # fake stale cache
        assert cache.last_indexed_path.is_file()

        rc = main([
            "recall", "workflow", "--path", str(workspace),
            "--problem-domain", "cli-design",
            "--rebuild-cache",
        ])
        assert rc == 0
        # last-indexed.json should have been invalidated by --rebuild-cache
        assert not cache.last_indexed_path.is_file()
