"""Cross-layer (semantic) validation.

Each layer can be individually valid yet the blueprint still be broken because
the layers disagree. These checks enforce the agreements the task calls for.

Severity policy:
  * ERROR   -- referential integrity: a reference that points at nothing real
               (unknown entity/role/plan/permission, dangling foreign key).
               These make the blueprint invalid.
  * WARNING -- coverage / consistency heuristics that have legitimate exceptions
               (a derived API field with no column, an access rule that the
               endpoint does not enforce). Surfaced, but not fatal.
"""

from contracts import AppBlueprint, RuleType
from validation.report import Severity, ValidationReport


def validate_cross_layer(bp: AppBlueprint) -> ValidationReport:
    report = ValidationReport()
    _check_database(bp, report)
    _check_auth(bp, report)
    _check_api(bp, report)
    _check_ui(bp, report)
    _check_business_logic(bp, report)
    return report


# --- shared lookups -------------------------------------------------------

def _table_names(bp: AppBlueprint) -> set[str]:
    return {t.name for t in bp.database.tables}


def _columns_by_table(bp: AppBlueprint) -> dict[str, set[str]]:
    return {t.name: {c.name for c in t.columns} for t in bp.database.tables}


def _role_names(bp: AppBlueprint) -> set[str]:
    return {r.name for r in bp.auth.roles}


def _api_fields_by_entity(bp: AppBlueprint) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for ep in bp.api.endpoints:
        if ep.entity:
            names = {f.name for f in ep.request_fields} | {f.name for f in ep.response_fields}
            out.setdefault(ep.entity, set()).update(names)
    return out


# --- checks ---------------------------------------------------------------

def _check_database(bp: AppBlueprint, report: ValidationReport) -> None:
    tables = _table_names(bp)
    columns = _columns_by_table(bp)
    seen: set[str] = set()
    for table in bp.database.tables:
        if table.name in seen:
            report.add("database.duplicate_table", f"Duplicate table name '{table.name}'.",
                       f"database ({table.name})", Severity.ERROR, "database")
        seen.add(table.name)

        if not any(c.primary_key for c in table.columns):
            report.add("database.no_primary_key", f"Table '{table.name}' has no primary-key column.",
                       f"database.{table.name}", Severity.WARNING, "database")

        for col in table.columns:
            if not col.foreign_key:
                continue
            if "." not in col.foreign_key:
                report.add("database.bad_fk_format",
                           f"Foreign key '{col.foreign_key}' on {table.name}.{col.name} must be 'table.column'.",
                           f"database.{table.name}.{col.name}", Severity.ERROR, "database")
                continue
            ref_table, ref_col = col.foreign_key.split(".", 1)
            if ref_table not in tables:
                report.add("database.fk_unknown_table",
                           f"Foreign key {table.name}.{col.name} -> '{col.foreign_key}' points to unknown table '{ref_table}'.",
                           f"database.{table.name}.{col.name}", Severity.ERROR, "database")
            elif ref_col not in columns[ref_table]:
                report.add("database.fk_unknown_column",
                           f"Foreign key {table.name}.{col.name} -> '{col.foreign_key}' points to unknown column '{ref_col}' in '{ref_table}'.",
                           f"database.{table.name}.{col.name}", Severity.ERROR, "database")


def _check_auth(bp: AppBlueprint, report: ValidationReport) -> None:
    roles = _role_names(bp)
    permissions = {p.name for p in bp.auth.permissions}
    for role in bp.auth.roles:
        for perm in role.permissions:
            if perm not in permissions:
                report.add("auth.unknown_permission",
                           f"Role '{role.name}' grants permission '{perm}', which is not defined in auth.permissions.",
                           f"auth.roles ({role.name})", Severity.ERROR, "auth")
    if bp.auth.default_role is not None and bp.auth.default_role not in roles:
        report.add("auth.unknown_default_role",
                   f"default_role '{bp.auth.default_role}' is not a defined role.",
                   "auth.default_role", Severity.ERROR, "auth")
    if bp.auth.enabled and not roles:
        report.add("auth.no_roles", "Auth is enabled but no roles are defined.",
                   "auth.roles", Severity.WARNING, "auth")


def _check_api(bp: AppBlueprint, report: ValidationReport) -> None:
    tables = _table_names(bp)
    columns = _columns_by_table(bp)
    roles = _role_names(bp)
    for i, ep in enumerate(bp.api.endpoints):
        loc = f"api.endpoints[{i}] ({ep.method.value} {ep.path})"
        if ep.entity and ep.entity not in tables:
            report.add("api.unknown_entity",
                       f"Endpoint '{ep.path}' uses entity '{ep.entity}', which is not a database table.",
                       loc, Severity.ERROR, "api")
        for role in ep.allowed_roles:
            if role not in roles:
                report.add("api.unknown_role",
                           f"Endpoint '{ep.path}' allows role '{role}', which is not defined in auth.",
                           loc, Severity.ERROR, "api")
        # Coverage: request fields (writes) should map to a column. Derived/auth
        # fields legitimately do not, so this is a warning, not an error.
        if ep.entity and ep.entity in columns:
            for field in ep.request_fields:
                if field.name not in columns[ep.entity]:
                    report.add("api.field_without_column",
                               f"API request field '{field.name}' on '{ep.path}' has no matching column in table '{ep.entity}' (may be a derived/auth field).",
                               loc, Severity.WARNING, "api")


def _check_ui(bp: AppBlueprint, report: ValidationReport) -> None:
    tables = _table_names(bp)
    columns = _columns_by_table(bp)
    roles = _role_names(bp)
    api_fields = _api_fields_by_entity(bp)
    for pi, page in enumerate(bp.ui.pages):
        ploc = f"ui.pages[{pi}] ({page.path})"
        for role in page.allowed_roles:
            if role not in roles:
                report.add("ui.unknown_role",
                           f"Page '{page.path}' allows role '{role}', which is not defined in auth.",
                           ploc, Severity.ERROR, "ui")
        for ci, comp in enumerate(page.components):
            cloc = f"ui.pages[{pi}].components[{ci}] ({comp.name})"
            if comp.entity and comp.entity not in tables:
                report.add("ui.unknown_entity",
                           f"Component '{comp.name}' on '{page.path}' uses entity '{comp.entity}', which is not a database table.",
                           cloc, Severity.ERROR, "ui")
            if comp.entity:
                backing = api_fields.get(comp.entity, set()) | columns.get(comp.entity, set())
                for field in comp.fields:
                    if field.name not in backing:
                        report.add("ui.field_without_backing",
                                   f"UI field '{field.name}' in '{comp.name}' is not exposed by any API endpoint or column for '{comp.entity}'.",
                                   cloc, Severity.WARNING, "ui")


def _check_business_logic(bp: AppBlueprint, report: ValidationReport) -> None:
    roles = _role_names(bp)
    plans = set(bp.business_logic.plans)
    endpoint_roles = {ep.path: set(ep.allowed_roles) for ep in bp.api.endpoints}
    page_roles = {pg.path: set(pg.allowed_roles) for pg in bp.ui.pages}

    for i, rule in enumerate(bp.business_logic.rules):
        loc = f"business_logic.rules[{i}] ({rule.name})"
        for role in rule.roles:
            if role not in roles:
                report.add("business.unknown_role",
                           f"Rule '{rule.name}' references role '{role}', which is not defined in auth.",
                           loc, Severity.ERROR, "business")

        if rule.type == RuleType.PLAN_GATING:
            if rule.plan is None:
                report.add("business.plan_gating_no_plan",
                           f"Plan-gating rule '{rule.name}' has no plan set.",
                           loc, Severity.ERROR, "business")
            elif rule.plan not in plans:
                report.add("business.unknown_plan",
                           f"Plan-gating rule '{rule.name}' gates on plan '{rule.plan}', not in business_logic.plans {sorted(plans)}.",
                           loc, Severity.ERROR, "business")

        # "Admin-only endpoints actually require the admin role" and similar:
        # if a role_access rule names a real endpoint/page, the access should agree.
        if rule.type == RuleType.ROLE_ACCESS and rule.target and rule.roles:
            declared = set(rule.roles)
            for label, mapping in (("endpoint", endpoint_roles), ("page", page_roles)):
                if rule.target in mapping:
                    actual = mapping[rule.target]
                    if not actual:
                        report.add("business.access_not_enforced",
                                   f"Rule '{rule.name}' restricts '{rule.target}' to {sorted(declared)}, but that {label} enforces no role restriction.",
                                   loc, Severity.WARNING, "business")
                    elif actual != declared:
                        report.add("business.access_mismatch",
                                   f"Rule '{rule.name}' restricts '{rule.target}' to {sorted(declared)}, but the {label} allows {sorted(actual)}.",
                                   loc, Severity.WARNING, "business")
