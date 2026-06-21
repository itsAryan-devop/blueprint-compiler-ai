"""Output layer 2 of 5: the API schema (endpoints, methods, validation).

Each endpoint records the entity it touches, the fields it accepts and returns,
and which roles may call it. Those are the hooks that later let us prove every
UI field maps to an API field, every API field maps to a DB column, and every
admin-only route truly requires the admin role.
"""

from pydantic import Field

from contracts.common import FieldType, HTTPMethod, StrictModel


class APIField(StrictModel):
    name: str = Field(..., description="Field name in snake_case.")
    type: FieldType = Field(..., description="Field data type.")
    required: bool = Field(default=True, description="Whether the field is required.")
    description: str = Field(default="", description="What this field is.")


class Endpoint(StrictModel):
    name: str = Field(..., description="Short endpoint name, e.g. 'create_contact'.")
    method: HTTPMethod = Field(..., description="HTTP method.")
    path: str = Field(..., description="URL path starting with '/', e.g. '/contacts' or '/contacts/{id}'.")
    description: str = Field(default="", description="What the endpoint does.")
    entity: str | None = Field(
        default=None,
        description="The primary table this endpoint operates on, e.g. 'contacts'. Null for non-entity endpoints like '/login'.",
    )
    request_fields: list[APIField] = Field(
        default_factory=list,
        description="Fields accepted in the request body or query.",
    )
    response_fields: list[APIField] = Field(
        default_factory=list,
        description="Fields returned in the response.",
    )
    requires_auth: bool = Field(default=False, description="True if the caller must be authenticated.")
    allowed_roles: list[str] = Field(
        default_factory=list,
        description="Roles permitted to call this endpoint. Empty = any authenticated user (or public if requires_auth is false).",
    )


class APISchema(StrictModel):
    endpoints: list[Endpoint] = Field(..., min_length=1, description="All API endpoints.")
