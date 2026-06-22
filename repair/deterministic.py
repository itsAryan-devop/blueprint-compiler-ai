"""Tier 1 -- deterministic, code-only fixes (no LLM).

Each fixer re-derives the problem straight from the blueprint (the same way the
validators do) and applies a safe, obvious correction in place, recording a
before -> after entry in the repair log. These cover the common, unambiguous
cases; anything riskier is left for targeted regeneration (Tier 2).

Aliasing runs FIRST: a reference that is merely a case/plural variant of a real
name (e.g. 'Contact' or 'Contacts' for the table 'contacts') is rewritten to the
canonical name -- a free, correct match that avoids an expensive LLM regen.
"""

from contracts import AppBlueprint, RuleType
from contracts.auth import Permission
from contracts.common import FieldType
from contracts.database import Column
from repair.log import RepairLog, RepairTier


def apply_deterministic_fixes(bp: AppBlueprint, log: RepairLog) -> int:
    """Run every deterministic fixer once. Returns how many fixes were applied."""
    return (
        _fix_entity_aliases(bp, log)     # normalize entity names first ...
        + _fix_role_aliases(bp, log)     # ... and role names ...
        + _fix_unknown_plans(bp, log)    # ... before the add/drop/enforce fixers
        + _fix_missing_permissions(bp, log)
        + _fix_default_role(bp, log)
        + _fix_unknown_role_refs(bp, log)
        + _fix_access_enforcement(bp, log)
        + _fix_missing_primary_keys(bp, log)
    )


def _role_names(bp: AppBlueprint) -> set[str]:
    return {r.name for r in bp.auth.roles}


def _normalize(name: str) -> str:
    """Lower-case + naive singularize, for case-/plural-insensitive matching.

    Handles the common regular cases (Contacts/Contact/contact -> 'contact',
    Companies -> 'company'). Irregular plurals (people/person) won't match and
    fall through to regeneration -- that is fine, this only turns the easy,
    high-frequency variants into free matches.
    """
    n = name.strip().lower()
    if n.endswith("ies"):
        return n[:-3] + "y"
    for suffix in ("ses", "xes", "zes", "ches", "shes"):
        if n.endswith(suffix):
            return n[:-2]
    if n.endswith("s") and not n.endswith("ss"):
        return n[:-1]
    return n


def _fix_entity_aliases(bp: AppBlueprint, log: RepairLog) -> int:
    """Rewrite component/endpoint entities that are case/plural variants of a real table."""
    tables = {t.name for t in bp.database.tables}
    canonical: dict[str, str] = {}
    for table in bp.database.tables:
        canonical.setdefault(_normalize(table.name), table.name)
    fixes = 0

    for i, ep in enumerate(bp.api.endpoints):
        if ep.entity and ep.entity not in tables:
            match = canonical.get(_normalize(ep.entity))
            if match:
                log.record("api.unknown_entity", f"api.endpoints[{i}] ({ep.path})", RepairTier.DETERMINISTIC,
                           f"Normalized endpoint entity '{ep.entity}' to table '{match}'.", ep.entity, match)
                ep.entity = match
                fixes += 1

    for pi, page in enumerate(bp.ui.pages):
        for ci, comp in enumerate(page.components):
            if comp.entity and comp.entity not in tables:
                match = canonical.get(_normalize(comp.entity))
                if match:
                    log.record("ui.unknown_entity", f"ui.pages[{pi}].components[{ci}] ({comp.name})",
                               RepairTier.DETERMINISTIC,
                               f"Normalized component entity '{comp.entity}' to table '{match}'.", comp.entity, match)
                    comp.entity = match
                    fixes += 1
    return fixes


def _fix_role_aliases(bp: AppBlueprint, log: RepairLog) -> int:
    """Rewrite role references that are case/plural variants of a real role."""
    roles = _role_names(bp)
    canonical: dict[str, str] = {}
    for role in bp.auth.roles:
        canonical.setdefault(_normalize(role.name), role.name)

    fixes = 0

    def fix_role_list(role_list: list[str], loc: str, code: str) -> list[str]:
        nonlocal fixes
        result = []
        for role in role_list:
            if role in roles:
                result.append(role)
                continue
            match = canonical.get(_normalize(role))
            if match and match != role:
                log.record(code, loc, RepairTier.DETERMINISTIC,
                           f"Normalized role '{role}' to '{match}'.", role, match)
                result.append(match)
                fixes += 1
            else:
                result.append(role)  # exact-unknown -> left for the drop fixer
        return result

    for i, ep in enumerate(bp.api.endpoints):
        ep.allowed_roles = fix_role_list(ep.allowed_roles, f"api.endpoints[{i}] ({ep.path})", "api.unknown_role")
    for pi, page in enumerate(bp.ui.pages):
        page.allowed_roles = fix_role_list(page.allowed_roles, f"ui.pages[{pi}] ({page.path})", "ui.unknown_role")
    for ri, rule in enumerate(bp.business_logic.rules):
        rule.roles = fix_role_list(rule.roles, f"business_logic.rules[{ri}] ({rule.name})", "business.unknown_role")
    return fixes


def _fix_unknown_plans(bp: AppBlueprint, log: RepairLog) -> int:
    plans = set(bp.business_logic.plans)
    fixes = 0
    for rule in bp.business_logic.rules:
        if rule.type == RuleType.PLAN_GATING and rule.plan and rule.plan not in plans:
            before = str(sorted(plans))
            bp.business_logic.plans.append(rule.plan)
            plans.add(rule.plan)
            log.record("business.unknown_plan", f"business_logic ({rule.name})", RepairTier.DETERMINISTIC,
                       f"Added missing plan '{rule.plan}' referenced by rule '{rule.name}'.",
                       before, str(sorted(plans)))
            fixes += 1
    return fixes


def _fix_missing_permissions(bp: AppBlueprint, log: RepairLog) -> int:
    defined = {p.name for p in bp.auth.permissions}
    fixes = 0
    for role in bp.auth.roles:
        for perm in role.permissions:
            if perm not in defined:
                bp.auth.permissions.append(Permission(name=perm, description="(added by repair)"))
                defined.add(perm)
                log.record("auth.unknown_permission", f"auth.roles ({role.name})", RepairTier.DETERMINISTIC,
                           f"Defined missing permission '{perm}' granted by role '{role.name}'.", "", perm)
                fixes += 1
    return fixes


def _fix_default_role(bp: AppBlueprint, log: RepairLog) -> int:
    roles = _role_names(bp)
    if bp.auth.default_role is not None and bp.auth.default_role not in roles:
        before = bp.auth.default_role
        new = "user" if "user" in roles else (sorted(roles)[0] if roles else None)
        bp.auth.default_role = new
        log.record("auth.unknown_default_role", "auth.default_role", RepairTier.DETERMINISTIC,
                   f"default_role '{before}' is undefined; set to '{new}'.", before or "", new or "")
        return 1
    return 0


def _fix_unknown_role_refs(bp: AppBlueprint, log: RepairLog) -> int:
    """Drop role references that are not defined in auth -- from endpoints, pages,
    AND business rules (symmetric: no layer is left to expensive regen for this)."""
    roles = _role_names(bp)
    fixes = 0
    for i, ep in enumerate(bp.api.endpoints):
        bad = [r for r in ep.allowed_roles if r not in roles]
        if bad:
            before = str(ep.allowed_roles)
            ep.allowed_roles = [r for r in ep.allowed_roles if r in roles]
            log.record("api.unknown_role", f"api.endpoints[{i}] ({ep.path})", RepairTier.DETERMINISTIC,
                       f"Dropped undefined role(s) {bad} from endpoint '{ep.path}'.", before, str(ep.allowed_roles))
            fixes += 1
    for pi, page in enumerate(bp.ui.pages):
        bad = [r for r in page.allowed_roles if r not in roles]
        if bad:
            before = str(page.allowed_roles)
            page.allowed_roles = [r for r in page.allowed_roles if r in roles]
            log.record("ui.unknown_role", f"ui.pages[{pi}] ({page.path})", RepairTier.DETERMINISTIC,
                       f"Dropped undefined role(s) {bad} from page '{page.path}'.", before, str(page.allowed_roles))
            fixes += 1
    for ri, rule in enumerate(bp.business_logic.rules):
        bad = [r for r in rule.roles if r not in roles]
        if bad:
            before = str(rule.roles)
            rule.roles = [r for r in rule.roles if r in roles]
            log.record("business.unknown_role", f"business_logic.rules[{ri}] ({rule.name})", RepairTier.DETERMINISTIC,
                       f"Dropped undefined role(s) {bad} from rule '{rule.name}'.", before, str(rule.roles))
            fixes += 1
    return fixes


def _fix_access_enforcement(bp: AppBlueprint, log: RepairLog) -> int:
    """If a role_access rule names a page/endpoint that does not enforce it, enforce it."""
    roles = _role_names(bp)
    endpoints = {ep.path: ep for ep in bp.api.endpoints}
    pages = {pg.path: pg for pg in bp.ui.pages}
    fixes = 0
    for rule in bp.business_logic.rules:
        if rule.type != RuleType.ROLE_ACCESS or not rule.target or not rule.roles:
            continue
        valid = [r for r in rule.roles if r in roles]
        if not valid:
            continue  # cannot enforce roles that do not exist; left for other fixers
        for label, container in (("endpoint", endpoints.get(rule.target)), ("page", pages.get(rule.target))):
            if container is None or set(container.allowed_roles) == set(valid):
                continue
            before = str(container.allowed_roles)
            container.allowed_roles = list(valid)
            container.requires_auth = True
            log.record("business.access_not_enforced", f"{label} {rule.target}", RepairTier.DETERMINISTIC,
                       f"Enforced rule '{rule.name}': set {label} '{rule.target}' allowed_roles to {valid}.",
                       before, str(valid))
            fixes += 1
    return fixes


def _fix_missing_primary_keys(bp: AppBlueprint, log: RepairLog) -> int:
    fixes = 0
    for table in bp.database.tables:
        if any(c.primary_key for c in table.columns):
            continue
        existing_id = next((c for c in table.columns if c.name == "id"), None)
        if existing_id is not None:
            existing_id.primary_key = True
            log.record("database.no_primary_key", f"database.{table.name}", RepairTier.DETERMINISTIC,
                       f"Marked existing 'id' column as primary key in '{table.name}'.", "", "id")
        else:
            table.columns.insert(0, Column(name="id", type=FieldType.UUID, primary_key=True,
                                           description="(added by repair)"))
            log.record("database.no_primary_key", f"database.{table.name}", RepairTier.DETERMINISTIC,
                       f"Added an 'id' primary-key column to table '{table.name}'.", "", "id")
        fixes += 1
    return fixes
