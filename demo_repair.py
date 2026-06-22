r"""
Phase 5 demo -- the tiered repair engine in action.

Run with:  .\venv\Scripts\python.exe demo_repair.py

Part 1  STRUCTURAL repair (no LLM): a dict with hallucinated fields is cleaned
        deterministically until it satisfies the contract.
Part 2  CROSS-LAYER repair (no LLM): a blueprint with six planted logical bugs
        (incl. a PascalCase entity alias and an undefined role inside a rule) is
        fixed by the deterministic tier, with a before -> after repair log.
Part 3  TARGETED REGENERATION (LLM): a bug code cannot safely fix (a component
        pointing at a non-existent table) is repaired by re-asking the model for
        ONLY the broken layer.
"""

import copy

from contracts import AppBlueprint
from demo_contracts import build_crm_blueprint
from repair import repair_blueprint, repair_raw
from validation import validate_blueprint


def show_log(log) -> None:
    print(f"  repair: {log.summary()}")
    for a in log.actions:
        print(f"    [{a.tier.value}] {a.issue_code} @ {a.location}: {a.description}")
        if a.before or a.after:
            print(f"        before={a.before!r}  after={a.after!r}")


def main() -> None:
    base = build_crm_blueprint().model_dump(mode="json")

    print("=" * 72)
    print("PART 1 -- STRUCTURAL repair (drop hallucinated fields, no LLM)")
    print("=" * 72)
    bad = copy.deepcopy(base)
    bad["ui"]["pages"][1]["components"][0]["color"] = "blue"             # hallucinated
    bad["database"]["tables"][0]["columns"][0]["auto_increment"] = True  # hallucinated
    print("Injected: ui...component.color and database...column.auto_increment")
    model, log = repair_raw(bad, AppBlueprint, use_llm=False)
    show_log(log)
    print(f"  result: {'VALID blueprint produced' if model is not None else 'could NOT repair'}")

    print("\n" + "=" * 72)
    print("PART 2 -- CROSS-LAYER repair (deterministic tier, no LLM)")
    print("=" * 72)
    bad = copy.deepcopy(base)
    bad["business_logic"]["rules"][1]["plan"] = "enterprise"             # plan not offered
    bad["auth"]["roles"][0]["permissions"].append("manage_billing")     # permission undefined
    bad["api"]["endpoints"][3]["allowed_roles"] = []                     # admin rule not enforced
    bad["ui"]["pages"][1]["allowed_roles"] = ["superadmin"]             # undefined role (page)
    bad["business_logic"]["rules"][0]["roles"] = ["admin", "superadmin"]  # undefined role in a RULE (P2.1)
    bad["ui"]["pages"][1]["components"][0]["entity"] = "Contact"          # PascalCase variant -> alias (P2.2)
    bp = AppBlueprint.model_validate(bad)
    print(f"  before: {validate_blueprint(bp).summary()}")
    result = repair_blueprint(bp, use_llm=False)
    show_log(result.log)
    print(f"  after : {result.remaining.summary()}  (success={result.success})")

    print("\n" + "=" * 72)
    print("PART 3 -- TARGETED REGENERATION (LLM): component -> non-existent table")
    print("=" * 72)
    bad = copy.deepcopy(base)
    bad["ui"]["pages"][1]["components"][0]["entity"] = "kontacts"       # not a real table
    bp = AppBlueprint.model_validate(bad)
    print(f"  before: {validate_blueprint(bp).summary()}")
    result = repair_blueprint(bp, use_llm=True)
    show_log(result.log)
    print(f"  after : {result.remaining.summary()}  (success={result.success})")


if __name__ == "__main__":
    main()
