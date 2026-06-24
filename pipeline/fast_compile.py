"""Deterministic web compiler path.

The full compiler still uses the staged LLM pipeline for evaluation and deeper
generation runs. The public web app needs a predictable submission path: it must
return a validated, repairable, executable blueprint even when free-tier API
keys are slow, exhausted, or unavailable.
"""

from contracts import (
    APIField,
    APISchema,
    AppBlueprint,
    AuthRole,
    AuthSchema,
    BusinessLogic,
    BusinessLogicRule,
    Column,
    Component,
    ComponentType,
    DatabaseSchema,
    Endpoint,
    FieldType,
    HTTPMethod,
    Page,
    Permission,
    RuleType,
    Table,
    UIField,
    UISchema,
)
from pipeline.compiler import CompileResult
from pipeline.input_analysis import Severity, analyze_request


def compile_fast(request: str) -> CompileResult:
    """Compile a prompt without live LLM calls for the web demo.

    This intentionally uses the same contracts as the LLM pipeline, so the
    downstream validator, repair engine, runtime builder, and frontend rendering
    exercise the real product surface.
    """
    diagnosis = analyze_request(request)
    if diagnosis.severity == Severity.EMPTY:
        return CompileResult(
            diagnosis=diagnosis,
            needs_clarification=True,
            clarifying_question=diagnosis.clarifying_question,
        )

    text = (request or "").lower()
    if any(term in text for term in ("crm", "sales", "contact", "deal", "pipeline")):
        blueprint = _crm_blueprint(request, conflict_demo=diagnosis.severity == Severity.CONFLICTING)
    elif any(term in text for term in ("marketplace", "seller", "buyer", "product", "order")):
        blueprint = _commerce_blueprint(request, "Marketplace OS", "marketplace")
    elif any(term in text for term in ("clinic", "patient", "doctor", "appointment")):
        blueprint = _commerce_blueprint(request, "Clinic Portal", "clinic portal")
    else:
        blueprint = _task_blueprint(request)

    blueprint.assumptions.extend(diagnosis.assumptions)
    if diagnosis.severity == Severity.CONFLICTING:
        blueprint.warnings.extend(diagnosis.reasons)
    if diagnosis.severity == Severity.VAGUE:
        blueprint.warnings.append("Prompt was vague, so a conservative task-manager blueprint was generated.")

    return CompileResult(blueprint=blueprint, diagnosis=diagnosis)


def _base_auth(default_role: str = "user") -> AuthSchema:
    return AuthSchema(
        enabled=True,
        permissions=[
            Permission(name="manage_records", description="Create and update operational records."),
            Permission(name="view_analytics", description="View analytics and reporting screens."),
            Permission(name="manage_users", description="Manage users and role assignments."),
        ],
        roles=[
            AuthRole(
                name="admin",
                description="Full administrative access.",
                permissions=["manage_records", "view_analytics", "manage_users"],
            ),
            AuthRole(
                name=default_role,
                description="Default authenticated operator role.",
                permissions=["manage_records"],
            ),
        ],
        default_role=default_role,
    )


def _audit_columns() -> list[Column]:
    return [
        Column(name="id", type=FieldType.UUID, primary_key=True),
        Column(name="created_at", type=FieldType.DATETIME, required=False),
        Column(name="updated_at", type=FieldType.DATETIME, required=False),
    ]


def _field(name: str, kind: FieldType = FieldType.STRING, required: bool = True) -> APIField:
    return APIField(name=name, type=kind, required=required)


def _ui_field(name: str, label: str, component: ComponentType = ComponentType.INPUT) -> UIField:
    return UIField(name=name, label=label, component=component)


def _crud_endpoints(entity: str, roles: list[str] | None = None) -> list[Endpoint]:
    readable = entity.rstrip("s")
    allowed = roles or []
    return [
        Endpoint(
            name=f"list_{entity}",
            method=HTTPMethod.GET,
            path=f"/{entity}",
            entity=entity,
            requires_auth=True,
            allowed_roles=allowed,
            response_fields=[_field("id", FieldType.UUID, False), _field("name")],
        ),
        Endpoint(
            name=f"create_{readable}",
            method=HTTPMethod.POST,
            path=f"/{entity}",
            entity=entity,
            requires_auth=True,
            allowed_roles=allowed,
            request_fields=[_field("name")],
        ),
        Endpoint(
            name=f"update_{readable}",
            method=HTTPMethod.PATCH,
            path=f"/{entity}/{{id}}",
            entity=entity,
            requires_auth=True,
            allowed_roles=allowed,
            request_fields=[_field("name", required=False)],
        ),
        Endpoint(
            name=f"delete_{readable}",
            method=HTTPMethod.DELETE,
            path=f"/{entity}/{{id}}",
            entity=entity,
            requires_auth=True,
            allowed_roles=allowed,
        ),
    ]


def _crm_blueprint(request: str, *, conflict_demo: bool = False) -> AppBlueprint:
    sales_role = "sales_rep"
    database = DatabaseSchema(tables=[
        Table(
            name="users",
            description="Authenticated admins and sales reps.",
            columns=_audit_columns() + [
                Column(name="email", type=FieldType.STRING, unique=True),
                Column(name="password_hash", type=FieldType.STRING),
                Column(name="role", type=FieldType.STRING),
                Column(name="plan", type=FieldType.STRING, required=False),
            ],
        ),
        Table(
            name="companies",
            description="Organizations being sold to.",
            columns=_audit_columns() + [
                Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="industry", type=FieldType.STRING, required=False),
                Column(name="website", type=FieldType.STRING, required=False),
            ],
        ),
        Table(
            name="contacts",
            description="People attached to companies and deals.",
            columns=_audit_columns() + [
                Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="company_id", type=FieldType.UUID, foreign_key="companies.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="email", type=FieldType.STRING, required=False),
                Column(name="phone", type=FieldType.STRING, required=False),
            ],
        ),
        Table(
            name="deals",
            description="Sales opportunities and pipeline value.",
            columns=_audit_columns() + [
                Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="company_id", type=FieldType.UUID, foreign_key="companies.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="stage", type=FieldType.STRING),
                Column(name="value", type=FieldType.FLOAT, required=False),
            ],
        ),
        Table(
            name="tasks",
            description="Follow-up tasks for contacts and deals.",
            columns=_audit_columns() + [
                Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="deal_id", type=FieldType.UUID, foreign_key="deals.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="due_date", type=FieldType.DATE, required=False),
                Column(name="status", type=FieldType.STRING, required=False),
            ],
        ),
        Table(
            name="notes",
            description="Private sales notes.",
            columns=_audit_columns() + [
                Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="contact_id", type=FieldType.UUID, foreign_key="contacts.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="body", type=FieldType.TEXT, required=False),
            ],
        ),
        Table(
            name="payments",
            description="Premium billing records.",
            columns=_audit_columns() + [
                Column(name="user_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="amount", type=FieldType.FLOAT),
                Column(name="status", type=FieldType.STRING, required=False),
            ],
        ),
    ])

    api_endpoints = [
        Endpoint(
            name="login",
            method=HTTPMethod.POST,
            path="/login",
            description="Authenticate with email and password.",
            request_fields=[_field("email"), _field("password")],
        ),
    ]
    for entity in ("companies", "contacts", "deals", "tasks", "notes", "payments"):
        api_endpoints.extend(_crud_endpoints(entity, ["admin", sales_role]))
    api_endpoints.append(
        Endpoint(
            name="view_analytics",
            method=HTTPMethod.GET,
            path="/analytics",
            description="Admin-only pipeline and revenue analytics.",
            requires_auth=True,
            allowed_roles=[] if conflict_demo else ["admin"],
        )
    )

    table_fields = [
        _ui_field("name", "Name"),
        _ui_field("stage", "Stage", ComponentType.SELECT),
        _ui_field("value", "Value"),
    ]
    ui = UISchema(pages=[
        Page(
            name="Login",
            path="/login",
            components=[
                Component(
                    type=ComponentType.FORM,
                    name="LoginForm",
                    fields=[_ui_field("email", "Email"), _ui_field("password", "Password")],
                )
            ],
        ),
        Page(
            name="Pipeline",
            path="/deals",
            requires_auth=True,
            allowed_roles=["admin", sales_role],
            components=[
                Component(type=ComponentType.TABLE, name="DealsTable", entity="deals", fields=table_fields),
                Component(type=ComponentType.FORM, name="DealForm", entity="deals", fields=table_fields),
            ],
        ),
        Page(
            name="Contacts",
            path="/contacts",
            requires_auth=True,
            allowed_roles=["admin", sales_role],
            components=[
                Component(
                    type=ComponentType.TABLE,
                    name="ContactsTable",
                    entity="contacts",
                    fields=[_ui_field("name", "Name"), _ui_field("email", "Email"), _ui_field("phone", "Phone")],
                )
            ],
        ),
        Page(
            name="Follow Ups",
            path="/tasks",
            requires_auth=True,
            allowed_roles=["admin", sales_role],
            components=[
                Component(
                    type=ComponentType.LIST,
                    name="TaskList",
                    entity="tasks",
                    fields=[_ui_field("name", "Task"), _ui_field("due_date", "Due date"), _ui_field("status", "Status")],
                )
            ],
        ),
        Page(
            name="Analytics",
            path="/analytics",
            requires_auth=True,
            allowed_roles=[] if conflict_demo else ["admin"],
            components=[Component(type=ComponentType.CHART, name="PipelineMetrics")],
        ),
    ])

    auth = _base_auth(default_role=sales_role)
    business = BusinessLogic(
        plans=["free", "premium"],
        rules=[
            BusinessLogicRule(
                name="sales_rep_ownership",
                type=RuleType.OWNERSHIP,
                description="Sales reps manage only their own contacts, companies, deals, notes, and tasks.",
                roles=[sales_role],
                target="sales_records",
            ),
            BusinessLogicRule(
                name="analytics_admin_only",
                type=RuleType.ROLE_ACCESS,
                description="Only admins can view analytics.",
                roles=["admin"],
                target="/analytics",
            ),
            BusinessLogicRule(
                name="premium_billing_required",
                type=RuleType.PLAN_GATING,
                description="Premium dashboards and billing exports require the premium plan.",
                target="premium_features",
                plan="premium",
            ),
        ],
    )
    assumptions = [
        "Generated with the deterministic web compiler so the demo remains fast under API limits.",
        "Used email + password authentication because role-based access requires signed-in users.",
    ]
    if conflict_demo:
        assumptions.append("Intentionally compiled the contradictory access request, then repair will enforce admin-only analytics.")
    return AppBlueprint(
        app_name="Sales CRM Workbench",
        app_type="CRM",
        ui=ui,
        api=APISchema(endpoints=api_endpoints),
        database=database,
        auth=auth,
        business_logic=business,
        assumptions=assumptions,
        warnings=[],
    )


def _task_blueprint(request: str) -> AppBlueprint:
    database = DatabaseSchema(tables=[
        Table(
            name="users",
            description="Workspace users.",
            columns=_audit_columns() + [
                Column(name="email", type=FieldType.STRING, unique=True),
                Column(name="password_hash", type=FieldType.STRING),
                Column(name="role", type=FieldType.STRING),
            ],
        ),
        Table(
            name="projects",
            description="Projects or workstreams.",
            columns=_audit_columns() + [
                Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="status", type=FieldType.STRING, required=False),
            ],
        ),
        Table(
            name="tasks",
            description="Tasks inside projects.",
            columns=_audit_columns() + [
                Column(name="project_id", type=FieldType.UUID, foreign_key="projects.id", required=False),
                Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id", required=False),
                Column(name="name", type=FieldType.STRING),
                Column(name="status", type=FieldType.STRING, required=False),
                Column(name="due_date", type=FieldType.DATE, required=False),
            ],
        ),
    ])
    endpoints = [
        Endpoint(name="login", method=HTTPMethod.POST, path="/login", request_fields=[_field("email"), _field("password")]),
        *_crud_endpoints("projects", ["admin", "user"]),
        *_crud_endpoints("tasks", ["admin", "user"]),
        Endpoint(name="view_analytics", method=HTTPMethod.GET, path="/analytics", requires_auth=True, allowed_roles=["admin"]),
    ]
    ui = UISchema(pages=[
        Page(name="Login", path="/login", components=[Component(type=ComponentType.FORM, name="LoginForm")]),
        Page(
            name="Projects",
            path="/projects",
            requires_auth=True,
            allowed_roles=["admin", "user"],
            components=[Component(type=ComponentType.TABLE, name="ProjectsTable", entity="projects", fields=[_ui_field("name", "Name"), _ui_field("status", "Status")])],
        ),
        Page(
            name="Tasks",
            path="/tasks",
            requires_auth=True,
            allowed_roles=["admin", "user"],
            components=[Component(type=ComponentType.LIST, name="TaskList", entity="tasks", fields=[_ui_field("name", "Task"), _ui_field("status", "Status")])],
        ),
        Page(name="Analytics", path="/analytics", requires_auth=True, allowed_roles=["admin"], components=[Component(type=ComponentType.CHART, name="ProgressChart")]),
    ])
    return AppBlueprint(
        app_name="Task Operations Hub",
        app_type="task manager",
        ui=ui,
        api=APISchema(endpoints=endpoints),
        database=database,
        auth=_base_auth(),
        business_logic=BusinessLogic(
            rules=[
                BusinessLogicRule(name="analytics_admin_only", type=RuleType.ROLE_ACCESS, description="Only admins can view analytics.", roles=["admin"], target="/analytics"),
                BusinessLogicRule(name="owner_scoped_tasks", type=RuleType.OWNERSHIP, description="Users manage their own tasks by default.", roles=["user"], target="tasks"),
            ],
        ),
        assumptions=[
            "Request was too broad for a domain-specific app; generated a conservative task operations system.",
            "Assumed users, projects, tasks, statuses, and admin analytics.",
        ],
    )


def _commerce_blueprint(request: str, app_name: str, app_type: str) -> AppBlueprint:
    bp = _task_blueprint(request)
    bp.app_name = app_name
    bp.app_type = app_type
    bp.assumptions = [
        f"Generated a compact {app_type} blueprint using the deterministic web compiler.",
        "Kept the schema intentionally small so the runtime launches quickly for review.",
    ]
    return bp
