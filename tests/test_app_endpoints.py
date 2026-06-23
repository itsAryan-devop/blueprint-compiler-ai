"""Tests for the Phase 11 web layer (no API calls)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from demo_contracts import build_crm_blueprint
from pipeline.compiler import CompileResult
from pipeline.input_analysis import InputDiagnosis, Severity


def _ok(assumptions=None) -> CompileResult:
    bp = build_crm_blueprint()
    bp.assumptions = assumptions or []
    return CompileResult(
        blueprint=bp,
        diagnosis=InputDiagnosis(severity=Severity.OK, assumptions=assumptions or []),
    )


def _clarify() -> CompileResult:
    return CompileResult(
        blueprint=None,
        diagnosis=InputDiagnosis(severity=Severity.EMPTY,
                                 clarifying_question="describe your app"),
        needs_clarification=True,
        clarifying_question="describe your app",
    )


def test_healthz():
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


def test_index_serves_html_form():
    body = TestClient(app).get("/").text
    assert "<textarea" in body and "/compile" in body


def test_compile_success_returns_blueprint_and_repair_log():
    with patch("app.main.compile_app", return_value=_ok()):
        r = TestClient(app).post("/compile", json={"prompt": "x"})
    assert r.status_code == 200
    data = r.json()
    assert "blueprint" in data and "validation" in data and "diagnosis" in data
    assert "repair_log" in data
    assert data["blueprint"]["app_name"] == "CRM App"


def test_compile_clarification_short_circuits():
    with patch("app.main.compile_app", return_value=_clarify()):
        r = TestClient(app).post("/compile", json={"prompt": ""})
    data = r.json()
    assert data["needs_clarification"] is True
    assert "describe" in data["clarifying_question"].lower()
    assert "blueprint" not in data


def test_compile_pipeline_crash_returns_502():
    with patch("app.main.compile_app", side_effect=RuntimeError("nope")):
        r = TestClient(app).post("/compile", json={"prompt": "x"})
    assert r.status_code == 502
    assert "nope" in r.json()["detail"]


def test_compile_rejects_missing_prompt_field():
    r = TestClient(app).post("/compile", json={})
    assert r.status_code == 422  # Pydantic body validation
