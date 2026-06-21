"""Stage 1 output: a clean, structured reading of the user's request.

Intent does NOT invent architecture. It only captures *what the user asked for*
(app type, features, roles) plus any gaps we had to fill (assumptions) or
contradictions we found (conflicts). Designing entities and flows is Stage 2.
"""

from pydantic import Field

from contracts.common import StrictModel


class IntentSpec(StrictModel):
    app_name: str = Field(
        ...,
        description="A short, human-friendly name for the app, inferred from the request.",
    )
    app_type: str = Field(
        ...,
        description="The category of app, e.g. 'CRM', 'task manager', 'e-commerce store'.",
    )
    summary: str = Field(
        ...,
        description="One or two sentences describing what the app does.",
    )
    features: list[str] = Field(
        ...,
        min_length=1,
        description="The distinct capabilities the user asked for, e.g. 'user login', 'contact management', 'analytics dashboard'.",
    )
    roles: list[str] = Field(
        default_factory=list,
        description="User roles mentioned or implied, e.g. 'admin', 'user'. Empty if the app has no concept of roles.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Decisions made to fill gaps when the request was vague. Each entry states what was unclear and what was assumed.",
    )
    conflicts: list[str] = Field(
        default_factory=list,
        description="Contradictions found in the request and how each was resolved, e.g. 'Asked for no login but also role-based access; assumed login is required.'",
    )
