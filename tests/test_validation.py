"""Unit tests for the cross-layer validators (no API calls)."""

from contracts import AppBlueprint
from demo_contracts import build_crm_blueprint
from validation import validate_blueprint, validate_raw


def test_golden_blueprint_is_valid():
    report = validate_blueprint(build_crm_blueprint())
    assert report.is_valid
    assert report.errors == []


def test_unknown_entity_is_caught():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["ui"]["pages"][1]["components"][0]["entity"] = "kontacts"
    report = validate_raw(bad)
    assert not report.is_valid
    assert any(i.code == "ui.unknown_entity" for i in report.errors)


def test_unknown_role_in_business_rule_is_caught():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["business_logic"]["rules"][0]["roles"] = ["superadmin"]
    report = validate_raw(bad)
    assert any(i.code == "business.unknown_role" for i in report.errors)


def test_unknown_plan_is_caught():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["business_logic"]["rules"][1]["plan"] = "enterprise"
    report = validate_raw(bad)
    assert any(i.code == "business.unknown_plan" for i in report.errors)


def test_dangling_foreign_key_is_caught():
    bad = build_crm_blueprint().model_dump(mode="json")
    for table in bad["database"]["tables"]:
        if table["name"] == "contacts":
            for column in table["columns"]:
                if column["name"] == "owner_id":
                    column["foreign_key"] = "users.uid"
    report = validate_raw(bad)
    assert any(i.code == "database.fk_unknown_column" for i in report.errors)


def test_structural_error_from_hallucinated_field():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["database"]["tables"][0]["columns"][0]["auto_increment"] = True
    report = validate_raw(bad)
    assert not report.is_valid
    assert any(i.layer == "structural" for i in report.errors)
