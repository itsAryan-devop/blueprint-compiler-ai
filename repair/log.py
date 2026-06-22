"""The repair log -- a record of every problem fixed and how.

Surfacing this (which tier did the fix, before -> after) is a top-1% signal: it
proves the system repairs *intelligently* rather than blindly retrying.
"""

from enum import Enum

from pydantic import BaseModel, Field

from contracts import AppBlueprint
from validation import ValidationReport


class RepairTier(str, Enum):
    DETERMINISTIC = "deterministic"   # fixed in code, no LLM
    REGEN = "targeted_regen"          # re-asked the LLM for ONLY the broken layer
    FAILED = "failed"                 # could not be fixed automatically


class RepairAction(BaseModel):
    issue_code: str
    location: str
    tier: RepairTier
    description: str
    before: str = ""
    after: str = ""


class RepairLog(BaseModel):
    actions: list[RepairAction] = Field(default_factory=list)

    def record(self, issue_code, location, tier, description, before="", after=""):
        self.actions.append(
            RepairAction(
                issue_code=issue_code, location=location, tier=tier,
                description=description, before=before, after=after,
            )
        )

    def summary(self) -> str:
        det = sum(1 for a in self.actions if a.tier == RepairTier.DETERMINISTIC)
        regen = sum(1 for a in self.actions if a.tier == RepairTier.REGEN)
        failed = sum(1 for a in self.actions if a.tier == RepairTier.FAILED)
        return f"{len(self.actions)} action(s): {det} deterministic, {regen} targeted-regen, {failed} failed"


class RepairResult(BaseModel):
    success: bool
    blueprint: AppBlueprint | None
    log: RepairLog
    remaining: ValidationReport
