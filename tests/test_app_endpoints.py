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
    assert "<textarea" in body and "Blueprint Compiler" in body


def test_frontend_assets_are_served():
    client = TestClient(app)
    assert client.get("/assets/styles.css").status_code == 200
    assert client.get("/assets/app.js").status_code == 200


def test_compile_success_returns_blueprint_and_repair_log():
    runtime = {
        "id": "test-runtime",
        "base_url": "/runtime/test-runtime",
        "docs_url": "/runtime/test-runtime/docs",
        "openapi_url": "/runtime/test-runtime/openapi.json",
    }
    # Default web mode is now "live" -- mock the live compile_app path.
    with patch("app.main.compile_app", return_value=_ok()), \
         patch("app.main._launch_runtime", return_value=runtime):
        r = TestClient(app).post("/compile", json={"prompt": "Build a CRM with contacts and analytics."})
    assert r.status_code == 200
    data = r.json()
    assert "blueprint" in data and "validation" in data and "diagnosis" in data
    assert "repair_log" in data
    assert data["blueprint"]["app_name"] == "CRM App"
    assert data["runtime"]["docs_url"].endswith("/docs")
    assert data["compiler_mode"] == "live-llm"


def test_compile_clarification_short_circuits():
    with patch("app.main.compile_app", return_value=_clarify()):
        r = TestClient(app).post("/compile", json={"prompt": ""})
    data = r.json()
    assert data["needs_clarification"] is True
    assert "describe" in data["clarifying_question"].lower()
    assert "blueprint" not in data


def test_compile_pipeline_crash_returns_502():
    with patch("app.main.compile_app", side_effect=RuntimeError("nope")):
        r = TestClient(app).post("/compile", json={"prompt": "Build a CRM with contacts and analytics."})
    assert r.status_code == 502
    assert "RuntimeError" in r.json()["detail"]
    assert "nope" not in r.json()["detail"]



def test_conflicting_prompt_records_assumptions_in_diagnosis():
    """A self-contradictory prompt -- the deterministic Phase 8 analyzer should
    flag it as 'conflicting' and inject a resolution assumption, regardless of
    what the downstream LLM stage does with the repair log."""
    r = TestClient(app).post(
        "/compile",
        json={
            "prompt": (
                "Build a CRM with no login or users, but also add admin-only "
                "analytics, sales-rep permissions, private customer records, "
                "and role-based access control."
            )
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["diagnosis"]["severity"] == "conflicting"
    assert data["diagnosis"]["assumptions"]      # Phase 8 added a resolution
    assert data["blueprint"]["assumptions"]      # ...which carried into the blueprint


def test_compile_rejects_missing_prompt_field():
    r = TestClient(app).post("/compile", json={})
    assert r.status_code == 422  # Pydantic body validation


def test_generated_runtime_is_mounted_and_reachable(tmp_path):
    import app.main as main

    with patch.object(main, "RUNTIME_DATA_DIR", tmp_path):
        runtime = main._launch_runtime(build_crm_blueprint())

    client = TestClient(app)
    response = client.get(f"{runtime['base_url']}/")
    assert response.status_code == 200
    assert response.json()["app"] == "CRM App"
    assert client.get(runtime["openapi_url"]).status_code == 200
    assert list(tmp_path.glob("*.sqlite"))
