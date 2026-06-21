"""Output layer 5 of 5: business logic (the enforceable rules).

This is where 'admins only see analytics' and 'premium features need the paid
plan' live in a structured, checkable form. Each rule names the roles, target,
and plan it concerns, so a later validator can confirm those actually exist.
"""

from enum import Enum

from pydantic import Field

from contracts.common import StrictModel


class RuleType(str, Enum):
    ROLE_ACCESS = "role_access"      # restrict a target to specific roles
    PLAN_GATING = "plan_gating"      # restrict a target to a paid plan
    OWNERSHIP = "ownership"          # users may only touch their own records
    VALIDATION = "validation"        # value or field constraints
    OTHER = "other"


class BusinessLogicRule(StrictModel):
    name: str = Field(..., description="Short rule name, e.g. 'analytics_admin_only'.")
    type: RuleType = Field(..., description="The category of rule.")
    description: str = Field(..., description="The rule in plain language.")
    roles: list[str] = Field(
        default_factory=list,
        description="Roles this rule references (each must exist in the auth schema).",
    )
    target: str | None = Field(
        default=None,
        description="What the rule guards: an endpoint path, page path, entity, or feature.",
    )
    plan: str | None = Field(
        default=None,
        description="For plan_gating, the plan that unlocks the target (must be in BusinessLogic.plans); otherwise null.",
    )


class BusinessLogic(StrictModel):
    plans: list[str] = Field(
        default_factory=list,
        description="Subscription plans the app offers, e.g. ['free', 'premium']. Empty if the app has none.",
    )
    rules: list[BusinessLogicRule] = Field(
        default_factory=list,
        description="Enforceable business rules.",
    )
