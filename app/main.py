"""Public FastAPI server for the compiler and generated app runtimes."""

from __future__ import annotations

import logging
import os
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline import compile_app
from repair import repair_blueprint
from runtime import build_app

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
RUNTIME_DATA_DIR = Path(os.getenv("RUNTIME_DATA_DIR", ".runtime_data")).resolve()

app = FastAPI(
    title="Blueprint Compiler",
    description="English prompt to a validated, repaired, executable app blueprint.",
    version="1.0.0",
)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

_runtime_lock = threading.Lock()


class CompileRequest(BaseModel):
    prompt: str = Field(
        ...,
        max_length=10_000,
        description="The English app description.",
    )


def _launch_runtime(blueprint) -> dict[str, str]:
    """Build and mount one isolated generated app with a persistent SQLite DB."""
    runtime_id = uuid.uuid4().hex[:12]
    RUNTIME_DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = RUNTIME_DATA_DIR / f"{runtime_id}.sqlite"
    runtime_app, _ = build_app(blueprint, str(db_path))
    base_url = f"/runtime/{runtime_id}"

    # Route mutation is brief but protected because compile requests may overlap.
    with _runtime_lock:
        app.mount(base_url, runtime_app, name=f"runtime-{runtime_id}")

    return {
        "id": runtime_id,
        "base_url": base_url,
        "docs_url": f"{base_url}/docs",
        "openapi_url": f"{base_url}/openapi.json",
    }


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/compile")
def compile_endpoint(body: CompileRequest):
    """Run the real multi-stage LLM compiler, repair its output, then prove it
    executes by mounting a live runtime. If every provider key is exhausted the
    request fails honestly with a 502 -- we never fall back to a canned template
    that ignores the prompt."""
    try:
        result = compile_app(body.prompt)

        if result.needs_clarification:
            return JSONResponse({
                "needs_clarification": True,
                "clarifying_question": result.clarifying_question,
                "diagnosis": result.diagnosis.model_dump(),
            })

        repair_result = repair_blueprint(result.blueprint, use_llm=True)
        blueprint = repair_result.blueprint
        runtime = _launch_runtime(blueprint)
    except Exception as error:
        logger.exception("Compilation failed")
        raise HTTPException(
            status_code=502,
            detail=f"Compilation failed ({type(error).__name__}). All free-tier "
                   "keys may be rate-limited right now -- please retry in a minute.",
        ) from error

    return {
        "diagnosis": result.diagnosis.model_dump(),
        "blueprint": blueprint.model_dump(),
        "repair_log": [action.model_dump() for action in repair_result.log.actions],
        "validation": repair_result.remaining.model_dump(),
        "runtime": runtime,
        "compiler_mode": "live-llm",
    }


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
