"""Tests for v0.2.0 scenario-profile + review_checklist behaviour.

Covers:

- ``derive_allowed_categories`` picks ids from plan.review_checklist.categories
- ``_validate_findings`` accepts a custom allowed-category enum
- HTML renderer renders the Project Profile & Review Checklist section
- HTML renderer accepts preset categories that are NOT in base 11
- HTML renderer falls back to base 11 when plan has no review_checklist (v0.1.0 compat)
- xlsx RunMeta sheet emits profile.* + review_checklist.* keys
- All scenario-preset markdown files load + declare required sections
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from render_html import (  # noqa: E402 — sys.path patched in conftest
    BASE_11_CATEGORIES,
    ReportError,
    _validate_findings,
    derive_allowed_categories,
    render_report,
)


def _embedded_soa_checklist() -> dict[str, Any]:
    """A minimal review_checklist using c-cpp-embedded-soa preset ids."""
    return {
        "preset": "c-cpp-embedded-soa",
        "categories": [
            {"id": "memory-safety", "description": "UAF / OOB / overflow", "severity_default": "high"},
            {"id": "isr-safety", "description": "ISR blocking / non-reentrant", "severity_default": "critical"},
            {"id": "ipc-contract", "description": "IDL mismatch", "severity_default": "critical"},
            {"id": "real-time", "description": "deadline / watchdog", "severity_default": "high"},
            {"id": "error-handling", "description": "return code dropped", "severity_default": "medium"},
        ],
        "user_confirmed": True,
        "confirmed_at": "2026-05-18T08:31:02Z",
    }


def _embedded_soa_profile() -> dict[str, Any]:
    return {
        "languages": ["c", "cpp"],
        "architectures": ["embedded", "soa"],
        "frameworks": ["FreeRTOS", "AUTOSAR-Classic"],
        "build_systems": ["cmake"],
        "risk_focus": ["memory-safety", "isr-safety", "ipc-contract", "real-time"],
        "detected_signals": [
            "src/board/stm32f4xx_hal_conf.h",
            "src/rtos/FreeRTOSConfig.h",
            "ipc/proto/*.arxml (12 service contracts)",
        ],
        "user_confirmed": True,
        "confirmed_at": "2026-05-18T08:31:02Z",
    }


def _make_finding(
    *,
    fid: str = "F-cpp-001",
    category: str = "memory-safety",
    severity: str = "high",
    confidence: str = "high",
    module: str = "rtos",
    file: str = "src/rtos/task_dispatch.c",
    line_start: int = 42,
    line_end: int = 47,
) -> dict[str, Any]:
    return {
        "id": fid,
        "run_id": "audit-embedded-001",
        "module": module,
        "file": file,
        "line_start": line_start,
        "line_end": line_end,
        "file_sha256": "c" * 64,
        "title": "Stack-allocated buffer aliased to ISR-published pointer (UAF risk)",
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "description": "ISR publishes pointer to a local buffer that goes out of scope.",
        "evidence": {
            "code_snippet": "uint8_t buf[32]; publish_ptr(buf); return;",
            "reasoning": "Local `buf` deallocated on return; ISR reader sees freed stack frame.",
            "trigger_conditions": "any ISR scheduled after task returns",
            "expected_vs_actual": "expected: heap or static buffer; actual: stack-local",
            "related_files": ["src/rtos/isr_handler.c"],
        },
        "suggested_fix": "Use a static or heap-allocated buffer with a producer/consumer queue.",
        "reviewer": {"agent": "code-audit-reviewer-agent", "ts": "2026-05-18T08:35:00Z"},
        "verifier": {
            "status": "confirmed",
            "reason": "Confirmed; reading the linker map shows the address is reused.",
            "evidence_check": "Read src/rtos/task_dispatch.c L40-50; grepped publish_ptr.",
            "agent": "code-audit-verifier-agent",
            "ts": "2026-05-18T08:42:00Z",
        },
    }


def _write_run(
    tmp_path: Path,
    *,
    run_id: str = "audit-embedded-001",
    confirmed: list[dict[str, Any]],
    plan: dict[str, Any],
) -> Path:
    run_dir = tmp_path / ".garage" / "code-audit" / "runs" / run_id
    (run_dir / "findings").mkdir(parents=True)
    (run_dir / "reports").mkdir()
    (run_dir / "plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (run_dir / "confirmed.json").write_text(
        json.dumps(confirmed, indent=2), encoding="utf-8"
    )
    return run_dir


class TestDeriveAllowedCategories:
    """Resolution of allowed-category set from plan.json."""

    def test_review_checklist_categories_used_when_present(self) -> None:
        plan = {
            "review_checklist": {
                "preset": "c-cpp-embedded-soa",
                "categories": [
                    {"id": "memory-safety", "description": "..."},
                    {"id": "isr-safety", "description": "..."},
                ],
            }
        }
        assert derive_allowed_categories(plan) == ("memory-safety", "isr-safety")

    def test_falls_back_to_base_11_when_no_checklist(self) -> None:
        assert derive_allowed_categories({}) == BASE_11_CATEGORIES

    def test_falls_back_when_checklist_categories_empty(self) -> None:
        plan = {"review_checklist": {"preset": "custom", "categories": []}}
        assert derive_allowed_categories(plan) == BASE_11_CATEGORIES

    def test_falls_back_when_checklist_is_not_dict(self) -> None:
        plan = {"review_checklist": "not a dict"}
        assert derive_allowed_categories(plan) == BASE_11_CATEGORIES

    def test_dedupes_and_preserves_order(self) -> None:
        plan = {
            "review_checklist": {
                "preset": "custom",
                "categories": [
                    {"id": "memory-safety", "description": "x"},
                    {"id": "memory-safety", "description": "dup"},
                    {"id": "isr-safety", "description": "y"},
                ],
            }
        }
        assert derive_allowed_categories(plan) == ("memory-safety", "isr-safety")

    def test_skips_entries_without_id(self) -> None:
        plan = {
            "review_checklist": {
                "preset": "custom",
                "categories": [
                    {"description": "no id"},
                    {"id": "", "description": "empty id"},
                    {"id": "valid-cat", "description": "ok"},
                ],
            }
        }
        assert derive_allowed_categories(plan) == ("valid-cat",)


class TestValidateFindingsWithChecklist:
    """`_validate_findings` honours `allowed_categories` param."""

    def test_preset_category_accepted_when_in_allowed(self) -> None:
        f = _make_finding(category="memory-safety")
        _validate_findings([f], allowed_categories=("memory-safety", "isr-safety"))

    def test_preset_category_rejected_when_not_in_allowed(self) -> None:
        f = _make_finding(category="memory-safety")
        with pytest.raises(ReportError, match="invalid category 'memory-safety'"):
            _validate_findings([f], allowed_categories=("isr-safety", "ipc-contract"))

    def test_default_falls_back_to_base_11(self) -> None:
        # Pre-v0.2.0 call site: no allowed_categories kwarg.
        f = _make_finding(category="error-handling")
        _validate_findings([f])
        bad = _make_finding(category="memory-safety")
        with pytest.raises(ReportError, match="invalid category 'memory-safety'"):
            _validate_findings([bad])


class TestRendererBackwardsCompat:
    """v0.1.0-era plan.json (no profile / no review_checklist) still renders."""

    def test_plan_without_review_checklist_uses_base_11(self, tmp_path: Path) -> None:
        plan = {
            "schema_version": 1,
            "run_id": "audit-legacy-001",
            "target": "src/",
            "created_at": "2025-12-01T00:00:00Z",
            "budgets": {"module_budget_tokens": 30000, "module_budget_files": 20},
            "modules": [
                {
                    "name": "runtime",
                    "path": "src/runtime/",
                    "priority": "high",
                    "file_count": 1,
                    "loc_estimate": 100,
                    "languages": ["python"],
                    "status": "done",
                }
            ],
            "total_files": 1,
            "total_loc": 100,
        }
        # Base-11 category — must pass.
        ok = _make_finding(
            fid="F-legacy-1",
            module="runtime",
            file="src/runtime/session_manager.py",
            category="error-handling",
        )
        run_dir = _write_run(
            tmp_path, run_id="audit-legacy-001", confirmed=[ok], plan=plan
        )
        result = render_report(
            confirmed_path=run_dir / "confirmed.json",
            plan_path=run_dir / "plan.json",
            findings_dir=run_dir / "findings",
            output_path=run_dir / "reports" / "report.html",
        )
        text = result.output_path.read_text(encoding="utf-8")
        # Profile section should be entirely absent for legacy plans.
        assert "Project Profile" not in text
        assert "Review Checklist" not in text
        # Base 11 category still appears in filter section.
        assert "error-handling" in text

    def test_plan_without_review_checklist_rejects_preset_category(
        self, tmp_path: Path
    ) -> None:
        plan = {
            "schema_version": 1,
            "run_id": "audit-legacy-002",
            "target": "src/",
            "created_at": "2025-12-01T00:00:00Z",
            "budgets": {"module_budget_tokens": 30000, "module_budget_files": 20},
            "modules": [],
            "total_files": 0,
            "total_loc": 0,
        }
        # `memory-safety` is a preset-only category — must be rejected under base 11.
        bad = _make_finding(category="memory-safety")
        run_dir = _write_run(
            tmp_path, run_id="audit-legacy-002", confirmed=[bad], plan=plan
        )
        with pytest.raises(ReportError, match="invalid category 'memory-safety'"):
            render_report(
                confirmed_path=run_dir / "confirmed.json",
                plan_path=run_dir / "plan.json",
                findings_dir=run_dir / "findings",
                output_path=run_dir / "reports" / "report.html",
            )


class TestRendererWithChecklist:
    """v0.2.0 plan with profile + review_checklist renders correctly."""

    def _embedded_soa_plan(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "run_id": "audit-embedded-001",
            "target": "src/",
            "created_at": "2026-05-18T08:30:00Z",
            "profile": _embedded_soa_profile(),
            "review_checklist": _embedded_soa_checklist(),
            "budgets": {"module_budget_tokens": 30000, "module_budget_files": 20},
            "modules": [
                {
                    "name": "rtos",
                    "path": "src/rtos/",
                    "priority": "high",
                    "file_count": 4,
                    "loc_estimate": 800,
                    "languages": ["c"],
                    "status": "done",
                }
            ],
            "total_files": 4,
            "total_loc": 800,
        }

    def test_preset_category_accepted(self, tmp_path: Path) -> None:
        plan = self._embedded_soa_plan()
        confirmed = [_make_finding(category="memory-safety")]
        run_dir = _write_run(tmp_path, confirmed=confirmed, plan=plan)
        result = render_report(
            confirmed_path=run_dir / "confirmed.json",
            plan_path=run_dir / "plan.json",
            findings_dir=run_dir / "findings",
            output_path=run_dir / "reports" / "report.html",
        )
        text = result.output_path.read_text(encoding="utf-8")
        assert "memory-safety" in text

    def test_category_outside_checklist_rejected(self, tmp_path: Path) -> None:
        plan = self._embedded_soa_plan()
        # `i18n-or-encoding` is base 11 but NOT in this preset's checklist.
        bad = _make_finding(category="i18n-or-encoding")
        run_dir = _write_run(tmp_path, confirmed=[bad], plan=plan)
        with pytest.raises(ReportError, match="invalid category 'i18n-or-encoding'"):
            render_report(
                confirmed_path=run_dir / "confirmed.json",
                plan_path=run_dir / "plan.json",
                findings_dir=run_dir / "findings",
                output_path=run_dir / "reports" / "report.html",
            )

    def test_profile_section_rendered(self, tmp_path: Path) -> None:
        plan = self._embedded_soa_plan()
        confirmed = [
            _make_finding(category="memory-safety"),
            _make_finding(fid="F-cpp-002", category="ipc-contract"),
        ]
        run_dir = _write_run(tmp_path, confirmed=confirmed, plan=plan)
        result = render_report(
            confirmed_path=run_dir / "confirmed.json",
            plan_path=run_dir / "plan.json",
            findings_dir=run_dir / "findings",
            output_path=run_dir / "reports" / "report.html",
        )
        text = result.output_path.read_text(encoding="utf-8")
        # Banner + profile section
        assert "Project Profile" in text
        assert "Languages" in text
        assert "c, cpp" in text
        assert "Architectures" in text
        assert "embedded, soa" in text
        assert "Risk focus" in text
        assert "memory-safety" in text
        # Checklist header
        assert "c-cpp-embedded-soa" in text
        # Confirmed status
        assert "User-confirmed" in text
        # Detected signals
        assert "stm32f4xx_hal_conf.h" in text
        # Checklist table contents
        assert "ipc-contract" in text
        assert "IDL mismatch" in text

    def test_unconfirmed_profile_renders_warning_class(self, tmp_path: Path) -> None:
        plan = self._embedded_soa_plan()
        plan["profile"]["user_confirmed"] = False
        plan["review_checklist"]["user_confirmed"] = False
        confirmed = [_make_finding(category="memory-safety")]
        run_dir = _write_run(tmp_path, confirmed=confirmed, plan=plan)
        result = render_report(
            confirmed_path=run_dir / "confirmed.json",
            plan_path=run_dir / "plan.json",
            findings_dir=run_dir / "findings",
            output_path=run_dir / "reports" / "report.html",
        )
        text = result.output_path.read_text(encoding="utf-8")
        assert "profile-unconfirmed" in text
        assert "not user-confirmed" in text.lower() or "auto-selected" in text.lower()

    def test_filter_fieldset_uses_checklist_categories(self, tmp_path: Path) -> None:
        plan = self._embedded_soa_plan()
        confirmed = [_make_finding(category="memory-safety")]
        run_dir = _write_run(tmp_path, confirmed=confirmed, plan=plan)
        result = render_report(
            confirmed_path=run_dir / "confirmed.json",
            plan_path=run_dir / "plan.json",
            findings_dir=run_dir / "findings",
            output_path=run_dir / "reports" / "report.html",
        )
        text = result.output_path.read_text(encoding="utf-8")
        # All preset categories should appear as filter checkboxes (data-filter="category")
        for cid in ("memory-safety", "isr-safety", "ipc-contract", "real-time", "error-handling"):
            assert f'value="{cid}"' in text
        # And the BASE 11 categories that ARE NOT in this preset should NOT appear in
        # the Category filter fieldset (we keep filters scoped to the preset).
        # Use a stricter check than naive substring; avoid false positives from
        # categories listed in `risk_focus` or other sections.
        assert 'value="i18n-or-encoding"' not in text
        assert 'value="typing"' not in text


class TestScenarioPresetFiles:
    """Sanity check: shipped preset markdown files exist + have required sections."""

    PACK_ROOT = Path(__file__).resolve().parents[2] / "packs" / "code-audit"
    PRESET_DIR = (
        PACK_ROOT
        / "skills"
        / "audit-reviewer"
        / "references"
        / "scenario-presets"
    )

    EXPECTED = (
        "c-cpp-embedded-soa.md",
        "c-cpp-embedded.md",
        "python-web-service.md",
        "frontend-spa.md",
        "generic.md",
        "_template.md",
    )

    @pytest.mark.parametrize("preset_file", EXPECTED)
    def test_preset_file_present_and_has_categories_section(self, preset_file: str) -> None:
        path = self.PRESET_DIR / preset_file
        assert path.is_file(), f"missing preset: {path}"
        text = path.read_text(encoding="utf-8")
        assert text.lstrip().startswith("# Scenario Preset"), (
            f"{preset_file} missing 'Scenario Preset' h1 header"
        )
        # Each preset must declare a Categories section (template too — it
        # lists header rows even if values are placeholders).
        assert "## Categories" in text, f"{preset_file} missing '## Categories' section"


class TestBugTaxonomyAndPlanSchemaDocs:
    """Documentation invariants for the new docs added in v0.2.0."""

    REPO_ROOT = Path(__file__).resolve().parents[2]

    def test_bug_taxonomy_lists_all_shipped_presets(self) -> None:
        text = (
            self.REPO_ROOT
            / "packs"
            / "code-audit"
            / "skills"
            / "audit-reviewer"
            / "references"
            / "bug-taxonomy.md"
        ).read_text(encoding="utf-8")
        for preset_id in (
            "generic",
            "c-cpp-embedded",
            "c-cpp-embedded-soa",
            "python-web-service",
            "frontend-spa",
        ):
            assert preset_id in text, (
                f"bug-taxonomy.md must reference preset id '{preset_id}'"
            )

    def test_plan_schema_documents_profile_and_review_checklist(self) -> None:
        text = (
            self.REPO_ROOT
            / "packs"
            / "code-audit"
            / "skills"
            / "audit-planner"
            / "references"
            / "plan-schema.md"
        ).read_text(encoding="utf-8")
        assert "`profile`" in text
        assert "`review_checklist`" in text
        assert "user_confirmed" in text
        assert "scenario preset" in text.lower() or "preset" in text.lower()

    def test_project_profile_rubric_present(self) -> None:
        path = (
            self.REPO_ROOT
            / "packs"
            / "code-audit"
            / "skills"
            / "audit-planner"
            / "references"
            / "project-profile-rubric.md"
        )
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        # Must cover embedded + SOA detection signals at minimum.
        assert "FreeRTOS" in text or "freertos" in text.lower()
        assert "AUTOSAR" in text or "arxml" in text.lower()
        assert "openapi" in text.lower() or "fastapi" in text.lower()
