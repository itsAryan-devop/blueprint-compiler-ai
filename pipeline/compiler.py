"""The pipeline orchestrator -- runs the four compiler passes in order.

    request
      -> intent    (Stage 1)
      -> design    (Stage 2)
      -> schemas   (Stage 3, modular: database, auth, api, ui, business logic)
      -> refine    (Stage 4: assemble)
      -> AppBlueprint

Schema generation runs in dependency order (database -> api -> ui, auth ->
business logic) so each layer can be made consistent with the ones it builds on.
"""

from contracts import AppBlueprint
from pipeline.design import design_system
from pipeline.intent import extract_intent
from pipeline.refine import refine
from pipeline.schema_gen import (
    generate_api,
    generate_auth,
    generate_business_logic,
    generate_database,
    generate_ui,
)


def compile_app(request: str) -> AppBlueprint:
    """Compile an English app request into a validated AppBlueprint."""
    print("[1/4] intent extraction")
    intent = extract_intent(request)

    print("[2/4] system design")
    design = design_system(intent)

    print("[3/4] schema generation (modular, each with its own small schema)")
    database = generate_database(design)
    auth = generate_auth(design)
    api = generate_api(design, database)
    ui = generate_ui(design, api)
    business_logic = generate_business_logic(design, auth)

    print("[4/4] refinement / assembly")
    return refine(intent, ui, api, database, auth, business_logic)
