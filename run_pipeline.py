r"""
Multi-stage pipeline demo (Phases 3-5).

    English -> Intent -> Design -> Schemas (modular) -> Refine -> Blueprint
                                                  -> Validate -> Repair -> final

Four focused stages (each with only its OWN small schema, each later layer shown
the layers it depends on), then a cross-layer validation pass (Phase 4), then the
tiered repair engine (Phase 5) which fixes what it can and logs how.

Run with:
    .\venv\Scripts\python.exe run_pipeline.py
    .\venv\Scripts\python.exe run_pipeline.py "Build a todo app with projects and due dates"
"""

import sys

from pipeline import compile_app
from repair import repair_blueprint
from validation import validate_blueprint

DEFAULT_REQUEST = (
    "Build a CRM with login, contacts, dashboard, role-based access, and a "
    "premium plan with payments. Admins can see analytics."
)


def main() -> None:
    request = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_REQUEST
    print("=" * 72)
    print("MULTI-STAGE PIPELINE  --  English -> intent -> design -> schemas -> blueprint")
    print("=" * 72)
    print(f"Request: {request}\n")

    try:
        blueprint = compile_app(request)
    except Exception as error:
        print(f"\nPipeline failed: {type(error).__name__}: {error}")
        return

    print("\n--- FINAL BLUEPRINT (valid AppBlueprint) ---")
    print(blueprint.model_dump_json(indent=2))

    print("\n--- VALIDATION (Phase 4: cross-layer consistency) ---")
    report = validate_blueprint(blueprint)
    print(report.summary())
    for issue in report.issues:
        print(f"  [{issue.severity.value}] {issue.code} @ {issue.location}: {issue.message}")

    print("\n--- REPAIR (Phase 5: tiered, logged) ---")
    result = repair_blueprint(blueprint)
    blueprint = result.blueprint
    if result.log.actions:
        print(result.log.summary())
        for action in result.log.actions:
            print(f"  [{action.tier.value}] {action.issue_code} @ {action.location}: {action.description}")
    else:
        print("Nothing to repair.")
    print(f"After repair: {result.remaining.summary()}")

    print("\n" + "=" * 72)
    print("PIPELINE RESULT")
    print("=" * 72)
    print(f"App: {blueprint.app_name} ({blueprint.app_type})")
    print(
        f"  pages={len(blueprint.ui.pages)}  "
        f"endpoints={len(blueprint.api.endpoints)}  "
        f"tables={len(blueprint.database.tables)}  "
        f"roles={len(blueprint.auth.roles)}  "
        f"rules={len(blueprint.business_logic.rules)}"
    )
    print(f"Validation after repair: {result.remaining.summary()}")
    if blueprint.assumptions:
        print(f"Assumptions: {blueprint.assumptions}")
    if blueprint.warnings:
        print(f"Warnings: {blueprint.warnings}")
    print("=" * 72)


if __name__ == "__main__":
    main()
