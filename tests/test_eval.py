"""Phase 9 tests -- exercise the runner against the input analyzer without LLM
calls. We stub compile_app to simulate each outcome class."""

from unittest.mock import patch

import pytest

from contracts import (
    APISchema,
    AppBlueprint,
    AuthSchema,
    BusinessLogic,
    DatabaseSchema,
    UISchema,
)
from demo_contracts import build_crm_blueprint
from eval import Case, CaseResult, run_one, summary, to_table
from pipeline.compiler import CompileResult
from pipeline.input_analysis import InputDiagnosis, Severity


def _ok_result(assumptions: list[str] | None = None) -> CompileResult:
    bp = build_crm_blueprint()
    bp.assumptions = assumptions or []
    return CompileResult(
        blueprint=bp,
        diagnosis=InputDiagnosis(severity=Severity.OK, assumptions=assumptions or []),
    )


def _clarify_result() -> CompileResult:
    return CompileResult(
        blueprint=None,
        diagnosis=InputDiagnosis(severity=Severity.EMPTY, clarifying_question="huh?"),
        needs_clarification=True,
        clarifying_question="huh?",
    )


def test_compiles_case_is_scored_ok():
    case = Case("X1", "ok", "anything", "compiles")
    with patch("eval.runner.compile_app", return_value=_ok_result()):
        r = run_one(case)
    assert r.outcome == "compiled" and r.matched_expected and r.issues_after == 0


def test_clarifies_case_is_scored_ok():
    case = Case("X2", "empty", "", "clarifies")
    with patch("eval.runner.compile_app", return_value=_clarify_result()):
        r = run_one(case)
    assert r.outcome == "clarified" and r.matched_expected


def test_assumes_requires_recorded_assumptions():
    case = Case("X3", "vague", "make app", "assumes")
    # No assumptions -> should NOT count as 'assumes' satisfied.
    with patch("eval.runner.compile_app", return_value=_ok_result(assumptions=[])):
        bad = run_one(case)
    with patch("eval.runner.compile_app", return_value=_ok_result(assumptions=["a"])):
        good = run_one(case)
    assert not bad.matched_expected and good.matched_expected


def test_failed_compile_does_not_crash_runner():
    case = Case("X4", "boom", "x", "compiles")
    with patch("eval.runner.compile_app", side_effect=RuntimeError("nope")):
        r = run_one(case)
    assert r.outcome == "failed" and r.failure_type == "RuntimeError"


def test_summary_and_table_are_well_formed():
    results = [
        CaseResult("X1", "a", "compiles", "compiled", True, 1.2, repair_actions=2, regen_actions=1,
                   issues_before=2, issues_after=0, assumptions=1),
        CaseResult("X2", "b", "clarifies", "clarified", True, 0.01),
    ]
    s = summary(results)
    assert s["total"] == 2 and s["success_rate"] == 1.0
    assert "id" in to_table(results) and "yes" in to_table(results)
