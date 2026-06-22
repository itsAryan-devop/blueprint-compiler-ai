"""The repair orchestrator for a whole blueprint.

Loop, up to a hard cap of rounds:
  1. apply every deterministic fix (covers fixable errors AND fixable warnings),
  2. re-validate; stop when valid and stable,
  3. for any ERROR a code-only fix could not clear, regenerate just that layer,
  4. after the cap, record whatever is left as FAILED (structured failure).

Works on a deep copy, so the caller's blueprint is never mutated.
"""

from contracts import AppBlueprint
from repair.deterministic import apply_deterministic_fixes
from repair.log import RepairLog, RepairResult, RepairTier
from repair.regen import regenerate_layer
from validation import validate_cross_layer

# Validator issue.layer -> AppBlueprint attribute name.
_LAYER_ATTR = {
    "ui": "ui",
    "api": "api",
    "database": "database",
    "auth": "auth",
    "business": "business_logic",
}

# Regenerate in dependency order so an upstream fix (e.g. database) is in place
# before a layer that depends on it (api -> ui) is regenerated -- avoiding a
# cascade where we'd fix the same orphaned reference over multiple rounds.
_REGEN_ORDER = ["database", "auth", "api", "ui", "business_logic"]


def repair_blueprint(blueprint: AppBlueprint, *, max_rounds: int = 3, use_llm: bool = True) -> RepairResult:
    bp = blueprint.model_copy(deep=True)
    log = RepairLog()

    for _ in range(max_rounds):
        before = len(log.actions)
        apply_deterministic_fixes(bp, log)
        report = validate_cross_layer(bp)
        progressed = len(log.actions) > before

        if report.is_valid:
            if progressed:
                continue   # a fix may have revealed or cleared more -- recheck
            break          # valid and stable

        if progressed:
            continue       # errors remain but we made progress -- recheck

        # Deterministic fixes are exhausted and errors remain -> targeted regen.
        if use_llm and _regenerate_broken_layers(bp, report, log):
            continue
        break

    final = validate_cross_layer(bp)
    if not final.is_valid:
        for issue in final.errors:
            log.record(issue.code, issue.location, RepairTier.FAILED,
                       "Remained invalid after deterministic fixes and targeted regeneration.")
    return RepairResult(success=final.is_valid, blueprint=bp, log=log, remaining=final)


def _regenerate_broken_layers(bp: AppBlueprint, report, log: RepairLog) -> bool:
    by_layer: dict[str, list[str]] = {}
    for issue in report.errors:
        attr = _LAYER_ATTR.get(issue.layer)
        if attr:
            by_layer.setdefault(attr, []).append(issue.message)

    changed = False
    for attr in _REGEN_ORDER:                 # dependency order, not dict order
        if attr not in by_layer:
            continue
        messages = by_layer[attr]
        try:
            # regenerate_layer reads fresh context from bp, so a layer
            # regenerated here already sees any upstream layer fixed above it.
            new_layer = regenerate_layer(bp, attr, messages)
            setattr(bp, attr, new_layer)
            log.record(f"regen.{attr}", attr, RepairTier.REGEN,
                       f"Regenerated the '{attr}' layer to fix {len(messages)} error(s): {messages[0]}")
            changed = True
        except Exception as error:
            log.record(f"regen.{attr}", attr, RepairTier.FAILED,
                       f"Targeted regeneration of '{attr}' failed: {error}")
    return changed
