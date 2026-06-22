"""Structural repair -- make an untrusted raw dict satisfy a Pydantic contract.

Tier 1 (deterministic): drop hallucinated fields. We use Pydantic's own error
locations to find and delete the offending keys -- no fragile introspection.
Tier 2 (regen): if errors remain that we cannot safely fix (missing required
fields, type errors Pydantic could not coerce), re-ask the LLM with the exact
errors. Tier 3: give up honestly (return None) and log why.
"""

import copy
import json

from pydantic import ValidationError

from llm import generate_model
from repair.log import RepairLog, RepairTier


def _delete_at(data, loc) -> bool:
    *parents, last = loc
    node = data
    for key in parents:
        try:
            node = node[key]
        except (KeyError, IndexError, TypeError):
            return False
    if isinstance(node, dict) and last in node:
        del node[last]
        return True
    return False


def repair_raw(data: dict, schema, *, use_llm: bool = True, max_attempts: int = 3):
    """Return (validated model, RepairLog) or (None, RepairLog) if unrepairable."""
    log = RepairLog()
    current = copy.deepcopy(data)

    for attempt in range(1, max_attempts + 1):
        try:
            return schema.model_validate(current), log
        except ValidationError as error:
            extras = [e for e in error.errors() if e["type"] == "extra_forbidden"]
            if extras:
                for err in extras:
                    if _delete_at(current, err["loc"]):
                        log.record("structural.extra_forbidden",
                                   ".".join(str(p) for p in err["loc"]),
                                   RepairTier.DETERMINISTIC, "Dropped hallucinated field.")
                continue  # re-validate after dropping the extras

            # Nothing deterministic left to do -> targeted regeneration.
            messages = [f'{".".join(str(p) for p in e["loc"]) or "(root)"}: {e["msg"]}'
                        for e in error.errors()]
            if use_llm and attempt < max_attempts:
                prompt = (
                    "This JSON failed validation. Fix ONLY these problems and return corrected JSON:\n"
                    + "\n".join(f"- {m}" for m in messages)
                    + f"\n\nBad JSON:\n{json.dumps(current, indent=2)[:6000]}"
                )
                try:
                    fixed = generate_model(prompt, schema)
                    log.record("structural.regen", "(root)", RepairTier.REGEN,
                               f"Re-asked the LLM to fix {len(messages)} structural error(s).")
                    return fixed, log
                except Exception as regen_error:
                    log.record("structural.regen", "(root)", RepairTier.FAILED,
                               f"Regeneration failed: {regen_error}")
                    return None, log

            for m in messages:
                log.record("structural.unfixable", m, RepairTier.FAILED, m)
            return None, log

    return None, log
