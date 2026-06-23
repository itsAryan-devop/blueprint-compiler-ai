"""Execution layer.

Turns a validated blueprint into something that actually runs: real SQLite tables
(``runtime.db``) and live FastAPI routes with auth enforced (``runtime.api``).
If a blueprint cannot execute, the run is a failure -- emitting JSON is not
enough. Phase 7's "critical difference".
"""

from runtime.api import build_app
from runtime.auth import AuthEnforcer
from runtime.db import build_database, create_table_sql

__all__ = ["build_app", "build_database", "create_table_sql", "AuthEnforcer"]
