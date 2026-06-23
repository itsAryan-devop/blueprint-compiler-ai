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
    database = generate_database(design)
    auth = generate_auth(design)
    api = generate_api(design, database)
    ui = generate_ui(design, api)
    business_logic = generate_business_logic(design, auth)

    print("[4/4] refinement / assembly")
    blueprint = refine(intent, ui, api, database, auth, business_logic)
    return CompileResult(blueprint=blueprint, diagnosis=diagnosis)
