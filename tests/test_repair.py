"""Unit tests for the deterministic repair tier (no API calls)."""

from contracts import AppBlueprint
from demo_contracts import build_crm_blueprint
from repair import repair_blueprint, repair_raw
from validation import validate_blueprint


def test_deterministic_repair_fixes_multiple_cross_layer_bugs():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["business_logic"]["rules"][1]["plan"] = "enterprise"          # unknown plan
    bad["auth"]["roles"][0]["permissions"].append("manage_billing")  # undefined permission
    bad["ui"]["pages"][1]["allowed_roles"] = ["superadmin"]          # undefined role
    blueprint = AppBlueprint.model_validate(bad)
    assert not validate_blueprint(blueprint).is_valid

    result = repair_blueprint(blueprint, use_llm=False)
    assert result.success
    assert result.remaining.is_valid
    assert len(result.log.actions) >= 3


def test_entity_alias_is_normalized_without_llm():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["ui"]["pages"][1]["components"][0]["entity"] = "Contact"  # PascalCase variant
    blueprint = AppBlueprint.model_validate(bad)

    result = repair_blueprint(blueprint, use_llm=False)
    assert result.success
    assert any("Normalized" in action.description for action in result.log.actions)


def test_business_rule_unknown_role_dropped_without_llm():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["business_logic"]["rules"][0]["roles"] = ["admin", "superadmin"]
    blueprint = AppBlueprint.model_validate(bad)

    result = repair_blueprint(blueprint, use_llm=False)
    assert result.success
    assert any(action.issue_code == "business.unknown_role" for action in result.log.actions)


def test_structural_repair_drops_hallucinated_field_without_llm():
    bad = build_crm_blueprint().model_dump(mode="json")
    bad["ui"]["pages"][1]["components"][0]["color"] = "blue"  # not in the contract
    model, log = repair_raw(bad, AppBlueprint, use_llm=False)
    assert model is not None
    assert any(action.issue_code == "structural.extra_forbidden" for action in log.actions)
