"""Stage 4 -- Refinement / assembly.

Combines the four schemas + business logic + intent metadata into the final
AppBlueprint. Cross-layer consistency was already built in *by construction*
during schema generation (each layer saw its dependencies). Rigorous cross-layer
VALIDATION arrives in Phase 4 and automatic REPAIR in Phase 5. For now this stage
assembles the blueprint and carries forward the assumptions and resolved
conflicts surfaced during intent extraction.
"""

from contracts import (
    APISchema,
    AppBlueprint,
    AuthSchema,
    BusinessLogic,
    DatabaseSchema,
    IntentSpec,
    UISchema,
)


def refine(
    intent: IntentSpec,
    ui: UISchema,
    api: APISchema,
    database: DatabaseSchema,
    auth: AuthSchema,
    business_logic: BusinessLogic,
) -> AppBlueprint:
    warnings = [f"Resolved conflict: {conflict}" for conflict in intent.conflicts]

    return AppBlueprint(
        app_name=intent.app_name,
        app_type=intent.app_type,
        ui=ui,
        api=api,
        database=database,
        auth=auth,
        business_logic=business_logic,
        assumptions=list(intent.assumptions),
        warnings=warnings,
    )
