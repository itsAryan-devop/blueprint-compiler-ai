"""Structural validation: does a raw dict satisfy the AppBlueprint contract?

This is the cheap, deterministic, code-only layer -- no LLM. It turns Pydantic's
ValidationError into our own located ValidationIssues, and returns the parsed
blueprint when the structure is sound (so cross-layer checks can run next).
"""

from pydantic import ValidationError

from contracts import AppBlueprint
from validation.report import Severity, ValidationReport


def validate_structure(data: dict) -> tuple[AppBlueprint | None, ValidationReport]:
    """Parse a raw dict into an AppBlueprint.

    Returns (blueprint, empty_report) on success, or (None, report_with_errors)
    if the dict does not satisfy the contract (missing fields, wrong types,
    hallucinated keys, ...).
    """
    report = ValidationReport()
    try:
        blueprint = AppBlueprint.model_validate(data)
        return blueprint, report
    except ValidationError as error:
        for err in error.errors():
            location = ".".join(str(part) for part in err["loc"]) or "(root)"
            report.add(
                code=f"structural.{err['type']}",
                message=err["msg"],
                location=location,
                severity=Severity.ERROR,
                layer="structural",
            )
        return None, report
