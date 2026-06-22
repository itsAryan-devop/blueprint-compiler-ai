"""Validators: structural (contract) + semantic (cross-layer) checks.

Use ``validate_blueprint`` when you already have a typed AppBlueprint (e.g. from
the pipeline); use ``validate_raw`` for an untrusted dict (e.g. in the Phase 5
repair loop), which runs the structural pass first and only then cross-layer.
"""

from contracts import AppBlueprint
from validation.cross_layer import validate_cross_layer
from validation.report import Severity, ValidationIssue, ValidationReport
from validation.structural import validate_structure


def validate_blueprint(blueprint: AppBlueprint) -> ValidationReport:
    """Cross-layer validation of an already-structurally-valid blueprint."""
    return validate_cross_layer(blueprint)


def validate_raw(data: dict) -> ValidationReport:
    """Full validation from an untrusted dict: structural first, then cross-layer."""
    blueprint, report = validate_structure(data)
    if blueprint is None:
        return report  # structural errors -> cross-layer can't run meaningfully
    report.issues.extend(validate_cross_layer(blueprint).issues)
    return report


__all__ = [
    "validate_blueprint",
    "validate_raw",
    "validate_structure",
    "validate_cross_layer",
    "ValidationReport",
    "ValidationIssue",
    "Severity",
]
