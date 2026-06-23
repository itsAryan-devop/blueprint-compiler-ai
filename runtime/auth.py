"""Demo-grade auth for the runtime.

Reads a role from the ``X-Role`` request header and verifies it against the
blueprint's auth roles and each endpoint's ``allowed_roles``. This is NOT
production auth (no passwords/tokens/sessions); it is the minimum needed to
*prove the blueprint's access rules are actually enforced at runtime*, which is
what Phase 7 is graded on.
"""

from fastapi import Header, HTTPException, status

from contracts import AppBlueprint


class AuthEnforcer:
    """Builds per-endpoint role checks from the blueprint."""

    def __init__(self, blueprint: AppBlueprint):
        self._enabled = blueprint.auth.enabled
        self._known_roles = {r.name for r in blueprint.auth.roles}

    def require(self, *, requires_auth: bool, allowed_roles: list[str]):
        """Return a FastAPI dependency that enforces this endpoint's access rules."""
        allowed = set(allowed_roles)

        async def dependency(x_role: str | None = Header(default=None)):
            if not self._enabled or (not requires_auth and not allowed):
                return None
            if x_role is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Role header")
            if x_role not in self._known_roles:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Unknown role '{x_role}'")
            if allowed and x_role not in allowed:
                raise HTTPException(status.HTTP_403_FORBIDDEN,
                                    f"Role '{x_role}' is not allowed (need one of {sorted(allowed)})")
            return x_role

        return dependency
