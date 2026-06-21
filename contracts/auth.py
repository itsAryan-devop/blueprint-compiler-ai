"""Output layer 4 of 5: the auth system (roles and permissions).

``enabled`` lets an app legitimately have no login at all. When it is on, the
roles and permissions defined here are the single source of truth that every
``allowed_roles`` elsewhere (pages, endpoints, business rules) is checked against.
"""

from pydantic import Field

from contracts.common import StrictModel


class Permission(StrictModel):
    name: str = Field(..., description="Permission identifier, e.g. 'view_analytics'.")
    description: str = Field(default="", description="What this permission allows.")


class AuthRole(StrictModel):
    name: str = Field(..., description="Role name in lowercase, e.g. 'admin', 'user'.")
    description: str = Field(default="", description="What this role is.")
    permissions: list[str] = Field(
        default_factory=list,
        description="Permission names granted to this role (each must be a defined permission).",
    )


class AuthSchema(StrictModel):
    enabled: bool = Field(default=True, description="Whether the app has authentication at all.")
    roles: list[AuthRole] = Field(default_factory=list, description="All user roles.")
    permissions: list[Permission] = Field(
        default_factory=list,
        description="All permissions referenced by roles.",
    )
    default_role: str | None = Field(
        default=None,
        description="Role assigned to new users, e.g. 'user'. Must match a defined role.",
    )
