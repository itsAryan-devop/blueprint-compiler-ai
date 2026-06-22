r"""
Phase 4 demo -- proof the validator can say precisely WHAT is wrong and WHERE.

Run with:  .\venv\Scripts\python.exe demo_validation.py

1. Validates the golden CRM blueprint  -> VALID (0 errors).
2. Validates four deliberately broken variants, each with ONE planted bug, and
   shows the exact issue caught:
     - a UI component pointing at a non-existent table
     - a business rule referencing a non-existent role
     - plan gating on a non-existent plan
     - a foreign key pointing at a non-existent column

No LLM is used -- this tests the validator logic deterministically.
"""

import copy

from demo_contracts import build_crm_blueprint
from validation import validate_blueprint, validate_raw


def show(report) -> None:
    print(f"  {report.summary()}")
    for issue in report.issues:
        print(f"    [{issue.severity.value}] {issue.code} @ {issue.location}")
        print(f"        {issue.message}")


def main() -> None:
    print("=" * 72)
    print("1) GOLDEN CRM blueprint (built from our contracts)")
    print("=" * 72)
    good = build_crm_blueprint()
    show(validate_blueprint(good))

    # Plant bugs on a raw JSON dict so we also exercise validate_raw (structural
    # pass + cross-layer pass). Each planted value is itself structurally valid.
    base = good.model_dump(mode="json")

    print("\n" + "=" * 72)
    print("2) BROKEN: a component points at a non-existent table 'kontacts'")
    print("=" * 72)
    bad = copy.deepcopy(base)
    bad["ui"]["pages"][1]["components"][0]["entity"] = "kontacts"
    show(validate_raw(bad))

    print("\n" + "=" * 72)
    print("3) BROKEN: a business rule references an undefined role 'superadmin'")
    print("=" * 72)
    bad = copy.deepcopy(base)
    bad["business_logic"]["rules"][0]["roles"] = ["superadmin"]
    show(validate_raw(bad))

    print("\n" + "=" * 72)
    print("4) BROKEN: plan gating on a non-existent plan 'enterprise'")
    print("=" * 72)
    bad = copy.deepcopy(base)
    bad["business_logic"]["rules"][1]["plan"] = "enterprise"
    show(validate_raw(bad))

    print("\n" + "=" * 72)
    print("5) BROKEN: a foreign key points at a non-existent column 'users.uid'")
    print("=" * 72)
    bad = copy.deepcopy(base)
    for table in bad["database"]["tables"]:
        if table["name"] == "contacts":
            for col in table["columns"]:
                if col["name"] == "owner_id":
                    col["foreign_key"] = "users.uid"
    show(validate_raw(bad))


if __name__ == "__main__":
    main()
