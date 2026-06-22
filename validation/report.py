"""The shape of a validation result: a list of precise, located issues.

The whole point of Phase 4 is that the system can say *exactly* what is wrong
and where, so a human (or the Phase 5 repair engine) can act on it. ERROR-level
issues make a blueprint invalid; WARNING-level issues flag things worth a look
that are not fatal (e.g. a derived API field with no database column).
"""

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    ERROR = "error"      # a real inconsistency: the blueprint is invalid
    WARNING = "warning"  # suspicious but not fatal


class ValidationIssue(BaseModel):
    code: str = Field(..., description="Machine-readable code, e.g. 'business.unknown_role'.")
    message: str = Field(..., description="Precise, human-readable explanation.")
    location: str = Field(..., description="Where it is, e.g. 'business_logic.rules[1] (premium_gating)'.")
    severity: Severity = Field(default=Severity.ERROR)
    layer: str = Field(default="", description="Area: database/api/ui/auth/business/cross/structural.")


class ValidationReport(BaseModel):
    issues: list[ValidationIssue] = Field(default_factory=list)

    def add(self, code, message, location, severity=Severity.ERROR, layer=""):
        self.issues.append(
            ValidationIssue(
                code=code, message=message, location=location, severity=severity, layer=layer
            )
        )

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == Severity.WARNING]

    @property
    def is_valid(self) -> bool:
        """A blueprint is valid when it has zero ERROR-level issues."""
        return len(self.errors) == 0

    def summary(self) -> str:
        verdict = "VALID" if self.is_valid else "INVALID"
        return f"{verdict} -- {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
