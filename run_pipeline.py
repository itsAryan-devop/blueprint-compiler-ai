r"""
Phase 3 demo -- the real multi-stage pipeline.

    English  ->  Intent  ->  Design  ->  Schemas (modular)  ->  Refine  ->  Blueprint

Unlike the walking skeleton (one giant call with the whole 12k-char schema), this
runs four focused stages, each with only its OWN small schema, and each later
layer is shown the layers it depends on -- so the output is cross-layer
consistent by construction and already valid against our contracts.

Run with:
    .\venv\Scripts\python.exe run_pipeline.py
    .\venv\Scripts\python.exe run_pipeline.py "Build a todo app with projects and due dates"
"""

import sys

from pipeline import compile_app

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

    print("\n" + "=" * 72)
    print("PHASE 3 RESULT")
    print("=" * 72)
    print(f"App: {blueprint.app_name} ({blueprint.app_type})")
    print(
        f"  pages={len(blueprint.ui.pages)}  "
        f"endpoints={len(blueprint.api.endpoints)}  "
        f"tables={len(blueprint.database.tables)}  "
        f"roles={len(blueprint.auth.roles)}  "
        f"rules={len(blueprint.business_logic.rules)}"
    )
    print("Every stage returned valid typed output; the blueprint assembled cleanly.")
    if blueprint.assumptions:
        print(f"Assumptions: {blueprint.assumptions}")
    if blueprint.warnings:
        print(f"Warnings: {blueprint.warnings}")
    print("=" * 72)


if __name__ == "__main__":
    main()
