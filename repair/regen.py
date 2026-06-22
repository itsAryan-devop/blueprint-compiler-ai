"""Tier 2 -- targeted regeneration (LLM).

When a code-only fix is not safe (e.g. a component points at a table that does
not exist -- which table did they mean?), re-ask the model for ONLY the broken
layer, handing it the exact errors and the list of valid names to use. This is
"regenerate the specific broken part", never a blind full retry of everything.
"""

import json

from contracts import APISchema, AuthSchema, BusinessLogic, DatabaseSchema, UISchema
from llm import generate_model

_LAYER_SCHEMAS = {
    "ui": UISchema,
    "api": APISchema,
    "database": DatabaseSchema,
    "auth": AuthSchema,
    "business_logic": BusinessLogic,
}


def _context_summary(bp) -> str:
    columns = {t.name: [c.name for c in t.columns] for t in bp.database.tables}
    return (
        f"tables: {[t.name for t in bp.database.tables]}\n"
        f"columns_by_table: {json.dumps(columns)}\n"
        f"roles: {[r.name for r in bp.auth.roles]}\n"
        f"plans: {bp.business_logic.plans}"
    )


def regenerate_layer(bp, layer_attr: str, error_messages: list[str]):
    """Re-generate one layer of the blueprint to fix the given errors. Returns a
    validated layer model (raises on failure, for the engine to catch)."""
    schema = _LAYER_SCHEMAS[layer_attr]
    current = getattr(bp, layer_attr).model_dump(mode="json")
    prompt = (
        f"You are repairing ONE layer of an app blueprint: the '{layer_attr}' layer.\n"
        "Fix ONLY these validation errors and change nothing else:\n"
        + "\n".join(f"- {msg}" for msg in error_messages)
        + "\n\nUse ONLY these existing names -- do NOT invent new tables, roles, or plans:\n"
        + _context_summary(bp)
        + f"\n\nCurrent (broken) '{layer_attr}' layer:\n{json.dumps(current, indent=2)}\n\n"
        + f"Return the corrected '{layer_attr}' layer as JSON."
    )
    return generate_model(prompt, schema)
