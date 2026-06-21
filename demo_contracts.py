r"""
Phase 1 demonstration -- proof that the contracts actually work.

Run with:  .\venv\Scripts\python.exe demo_contracts.py

It does three things:
  1. Builds the canonical CRM app from the task brief as a fully-typed
     AppBlueprint and prints it as JSON. This proves the five layers compose
     into one valid object, and gives us a golden reference of what the LLM
     should eventually produce.
  2. Feeds a BROKEN input missing a required field, and shows the contract
     rejecting it with a precise error.
  3. Feeds a BROKEN input with a hallucinated extra field, and shows the
     contract rejecting that too (thanks to extra='forbid').

This file is temporary Phase 1 scaffolding; it generates nothing with an LLM.
"""

from pydantic import ValidationError

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
    IntentSpec,
    Page,
    Permission,
    RuleType,
    Table,
    UIField,
    UISchema,
)


def build_crm_blueprint() -> AppBlueprint:
    """Hand-build the CRM example from the task brief, fully typed and
    cross-layer consistent (every UI field has an API field and a DB column)."""

    database = DatabaseSchema(
        tables=[
            Table(
                name="users",
                description="Application users.",
                columns=[
                    Column(name="id", type=FieldType.UUID, primary_key=True),
                    Column(name="email", type=FieldType.STRING, unique=True),
                    Column(name="password_hash", type=FieldType.STRING),
                    Column(name="role", type=FieldType.STRING, description="admin or user"),
                    Column(name="plan", type=FieldType.STRING, description="free or premium"),
                ],
            ),
            Table(
                name="contacts",
                description="CRM contacts.",
                columns=[
                    Column(name="id", type=FieldType.UUID, primary_key=True),
                    Column(name="owner_id", type=FieldType.UUID, foreign_key="users.id"),
                    Column(name="name", type=FieldType.STRING),
                    Column(name="email", type=FieldType.STRING),
                    Column(name="phone", type=FieldType.STRING, required=False),
                ],
            ),
            Table(
                name="payments",
                description="Payment records for premium plans.",
                columns=[
                    Column(name="id", type=FieldType.UUID, primary_key=True),
                    Column(name="user_id", type=FieldType.UUID, foreign_key="users.id"),
                    Column(name="amount", type=FieldType.FLOAT),
                    Column(name="created_at", type=FieldType.DATETIME),
                ],
            ),
        ]
    )

    api = APISchema(
        endpoints=[
            Endpoint(
                name="login",
                method=HTTPMethod.POST,
                path="/login",
                description="Authenticate a user.",
                request_fields=[
                    APIField(name="email", type=FieldType.STRING),
                    APIField(name="password", type=FieldType.STRING),
                ],
            ),
            Endpoint(
                name="list_contacts",
                method=HTTPMethod.GET,
                path="/contacts",
                entity="contacts",
                requires_auth=True,
                response_fields=[
                    APIField(name="name", type=FieldType.STRING),
                    APIField(name="email", type=FieldType.STRING),
                    APIField(name="phone", type=FieldType.STRING, required=False),
                ],
            ),
            Endpoint(
                name="create_contact",
                method=HTTPMethod.POST,
                path="/contacts",
                entity="contacts",
                requires_auth=True,
                request_fields=[
                    APIField(name="name", type=FieldType.STRING),
                    APIField(name="email", type=FieldType.STRING),
                    APIField(name="phone", type=FieldType.STRING, required=False),
                ],
            ),
            Endpoint(
                name="view_analytics",
                method=HTTPMethod.GET,
                path="/analytics",
                description="Admin-only analytics dashboard data.",
                requires_auth=True,
                allowed_roles=["admin"],
            ),
        ]
    )

    ui = UISchema(
        pages=[
            Page(
                name="Login",
                path="/login",
                components=[
                    Component(
                        type=ComponentType.FORM,
                        name="LoginForm",
                        entity=None,  # auth form, not entity CRUD
                        fields=[
                            UIField(name="email", label="Email"),
                            UIField(name="password", label="Password"),
                        ],
                    )
                ],
            ),
            Page(
                name="Contacts",
                path="/contacts",
                requires_auth=True,
                components=[
                    Component(
                        type=ComponentType.TABLE,
                        name="ContactsTable",
                        entity="contacts",
                        fields=[
                            UIField(name="name", label="Name"),
                            UIField(name="email", label="Email"),
                            UIField(name="phone", label="Phone"),
                        ],
                    )
                ],
            ),
            Page(
                name="Analytics",
                path="/analytics",
                requires_auth=True,
                allowed_roles=["admin"],
                components=[
                    Component(type=ComponentType.CHART, name="RevenueChart"),
                ],
            ),
        ]
    )

    auth = AuthSchema(
        enabled=True,
        permissions=[
            Permission(name="view_analytics", description="See the analytics dashboard."),
            Permission(name="manage_contacts", description="Create and edit contacts."),
        ],
        roles=[
            AuthRole(name="admin", permissions=["view_analytics", "manage_contacts"]),
            AuthRole(name="user", permissions=["manage_contacts"]),
        ],
        default_role="user",
    )

    business_logic = BusinessLogic(
        plans=["free", "premium"],
        rules=[
            BusinessLogicRule(
                name="analytics_admin_only",
                type=RuleType.ROLE_ACCESS,
                description="Only admins can view analytics.",
                roles=["admin"],
                target="/analytics",
            ),
            BusinessLogicRule(
                name="premium_gating",
                type=RuleType.PLAN_GATING,
                description="Premium features require the premium plan.",
                target="premium_features",
                plan="premium",
            ),
        ],
    )

    return AppBlueprint(
        app_name="CRM App",
        app_type="CRM",
        ui=ui,
        api=api,
        database=database,
        auth=auth,
        business_logic=business_logic,
        assumptions=[
            "Login method was unspecified; assumed standard email + password authentication.",
        ],
    )


def show_valid() -> None:
    print("=" * 72)
    print("1) VALID: the CRM blueprint builds and serializes to clean JSON")
    print("=" * 72)
    blueprint = build_crm_blueprint()
    print(blueprint.model_dump_json(indent=2))


def show_missing_required_field() -> None:
    print()
    print("=" * 72)
    print("2) BROKEN: IntentSpec is missing the required 'features' field")
    print("=" * 72)
    bad = {"app_name": "X", "app_type": "CRM", "summary": "this dict has no 'features' key"}
    try:
        IntentSpec.model_validate(bad)
        print("ERROR: this should NOT have validated!")
    except ValidationError as error:
        print("Rejected, as expected:")
        print(error)


def show_hallucinated_field() -> None:
    print()
    print("=" * 72)
    print("3) BROKEN: a Column with a hallucinated extra field 'auto_increment'")
    print("=" * 72)
    bad = {"name": "id", "type": "uuid", "auto_increment": True}
    try:
        Column.model_validate(bad)
        print("ERROR: this should NOT have validated!")
    except ValidationError as error:
        print("Rejected, as expected:")
        print(error)


if __name__ == "__main__":
    show_valid()
    show_missing_required_field()
    show_hallucinated_field()
