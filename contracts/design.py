"""Stage 2 output: the app's architecture, derived from the intent.

This is where we make the engineering decisions the user did not spell out:
which data entities exist, how they relate, what each role can do, the key user
flows, and the high-level business rules. The concrete UI / API / DB / Auth
schemas are built from this design in Stage 3.
"""

from pydantic import Field

from contracts.common import FieldType, RelationshipType, StrictModel


class EntityField(StrictModel):
    name: str = Field(..., description="Field name in snake_case, e.g. 'email', 'created_at'.")
    type: FieldType = Field(..., description="The data type of this field.")
    required: bool = Field(default=True, description="Whether this field must always have a value.")
    description: str = Field(default="", description="What this field stores.")


class Entity(StrictModel):
    name: str = Field(..., description="Entity name in PascalCase singular, e.g. 'Contact', 'User'.")
    description: str = Field(default="", description="What this entity represents.")
    fields: list[EntityField] = Field(..., min_length=1, description="The attributes of this entity.")


class Relationship(StrictModel):
    from_entity: str = Field(..., description="The owning entity (must match an Entity name).")
    to_entity: str = Field(..., description="The related entity (must match an Entity name).")
    type: RelationshipType = Field(..., description="Cardinality of the relationship.")
    description: str = Field(default="", description="Plain-language meaning, e.g. 'a User has many Contacts'.")


class Role(StrictModel):
    name: str = Field(..., description="Role name in lowercase, e.g. 'admin', 'user'.")
    description: str = Field(default="", description="What this role is for.")
    permissions: list[str] = Field(
        default_factory=list,
        description="High-level permissions, e.g. 'view_analytics', 'manage_contacts'.",
    )


class Flow(StrictModel):
    name: str = Field(..., description="Name of the user flow, e.g. 'User signs up and logs in'.")
    steps: list[str] = Field(..., min_length=1, description="Ordered steps the user takes.")


class BusinessRule(StrictModel):
    name: str = Field(..., description="Short rule name, e.g. 'premium_gating'.")
    description: str = Field(..., description="The rule in plain language.")
    applies_to: list[str] = Field(
        default_factory=list,
        description="Entities, features, or roles this rule constrains.",
    )


class SystemDesign(StrictModel):
    entities: list[Entity] = Field(..., min_length=1, description="The data models of the app.")
    relationships: list[Relationship] = Field(default_factory=list, description="How entities relate.")
    roles: list[Role] = Field(default_factory=list, description="User roles and their high-level permissions.")
    flows: list[Flow] = Field(default_factory=list, description="Key user journeys.")
    business_rules: list[BusinessRule] = Field(
        default_factory=list,
        description="Cross-cutting rules like gating and access control.",
    )
