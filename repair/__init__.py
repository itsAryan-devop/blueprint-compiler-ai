"""The repair engine (the core of the project).

Tiered, never brute-force:
  1. deterministic auto-fix   (no LLM)          -- repair/deterministic.py
  2. targeted regeneration    (LLM, one layer)  -- repair/regen.py
  3. structured failure       (honest give-up after a cap)

Every action is recorded in a RepairLog (which tier, before -> after).
Use ``repair_blueprint(bp)`` for cross-layer repair of a typed blueprint, and
``repair_raw(dict, schema)`` for structural repair of an untrusted dict.
"""

from repair.engine import repair_blueprint
from repair.log import RepairAction, RepairLog, RepairResult, RepairTier
from repair.structural import repair_raw

__all__ = [
    "repair_blueprint",
    "repair_raw",
    "RepairResult",
    "RepairLog",
    "RepairAction",
    "RepairTier",
]
