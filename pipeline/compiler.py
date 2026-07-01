"""The pipeline orchestrator -- runs the four compiler passes in order.

    request
      -> Phase 8 input analysis (deterministic: vague / conflicting / empty?)
      -> intent    (Stage 1)
      -> design    (Stage 2)
      -> schemas   (Stage 3, modular: database, auth, api, ui, business logic)
      -> refine    (Stage 4: assemble)
      -> AppBlueprint  OR  CompileResult(needs_clarification=True, ...)

Schema generation runs in dependency order (database -> api -> ui, auth ->
business logic) so each layer can be made consistent with the ones it builds on.
"""

import concurrent.futures

from pydantic import BaseModel

from contracts import AppBlueprint
from pipeline.design import design_system
from pipeline.input_analysis import InputDiagnosis, Severity, analyze_request
from pipeline.intent import extract_intent
from pipeline.refine import refine
from pipeline.schema_gen import (
    generate_api,
    generate_auth,
    generate_business_logic,
    generate_database,
    generate_ui,
)


class CompileResult(BaseModel):
    """The pipeline returns one of two things:

      * a built blueprint (success), with the diagnosis attached for transparency, OR
      * needs_clarification=True + a clarifying_question (when the prompt was
        empty / too short to compile anything from).

    Never a crash, never a silent guess -- this is what 'graceful failure' means.
    """
    blueprint: AppBlueprint | None = None
    diagnosis: InputDiagnosis
    needs_clarification: bool = False
    clarifying_question: str | None = None


def compile_app(request: str) -> CompileResult:
    """Compile an English app request into a validated AppBlueprint, gracefully."""
    diagnosis = analyze_request(request)
    print(f"[0/4] input analysis  -> severity={diagnosis.severity.value}", flush=True)
    for reason in diagnosis.reasons:
        print(f"        - {reason}")
    for assumption in diagnosis.assumptions:
        print(f"        + assume: {assumption}")

    if diagnosis.severity == Severity.EMPTY:
        # Refuse to call the AI on garbage input; return a clarifying question.
        return CompileResult(
            diagnosis=diagnosis,
            needs_clarification=True,
            clarifying_question=diagnosis.clarifying_question,
        )

    print("[1/4] intent extraction")
    intent = extract_intent(request, prior_assumptions=diagnosis.assumptions)

    print("[2/4] system design")
    design = design_system(intent)

    print("[3/4] schema generation (modular, each with its own small schema)")
    # Two independent dependency chains run in parallel to cut live latency:
    #   chain A: database -> api -> ui
    #   chain B: auth -> business_logic
    def _chain_a():
        db = generate_database(design)
        ap = generate_api(design, db)
        return db, ap, generate_ui(design, ap)

    def _chain_b():
        au = generate_auth(design)
        return au, generate_business_logic(design, au)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        fut_a = pool.submit(_chain_a)
        fut_b = pool.submit(_chain_b)
        database, api, ui = fut_a.result()
        auth, business_logic = fut_b.result()

    print("[4/4] refinement / assembly")
    blueprint = refine(intent, ui, api, database, auth, business_logic)
    return CompileResult(blueprint=blueprint, diagnosis=diagnosis)
