"""Stage 3 -- Schema generation (modular).

The four output schemas plus business logic, each produced by its OWN small,
focused call. Crucially, each layer is shown the layers it depends on -- the API
sees the database, the UI sees the API, business logic sees auth -- so the layers
line up *by construction*. That is the cheap way to get cross-layer consistency
before the validator (Phase 4) and the repair engine (Phase 5) enforce it
rigorously.
"""

from contracts import (
    APISchema,
    AuthSchema,
    BusinessLogic,
    DatabaseSchema,
    SystemDesign,
    UISchema,
)
from pipeline._prompting import run_stage, schema_text


def generate_database(design: SystemDesign) -> DatabaseSchema:
    prompt = (
        "You are the DATABASE-SCHEMA stage. Turn the design's entities into "
        "database tables. Table names in snake_case PLURAL (e.g. 'contacts'); "
        "columns in snake_case. Give every table an 'id' primary key, and add "
        "foreign-key columns (written as 'table.column', e.g. 'users.id') for "
        "relationships.\n\n"
        f"Return JSON matching this schema:\n{schema_text(DatabaseSchema)}\n\n"
        f"DESIGN:\n{design.model_dump_json(indent=2)}"
    )
    return run_stage("database", prompt, DatabaseSchema)


def generate_auth(design: SystemDesign) -> AuthSchema:
    prompt = (
        "You are the AUTH-SCHEMA stage. Define the roles and permissions from the "
        "design. Every permission a role references must also appear in the "
        "'permissions' list. Choose a sensible 'default_role' for new users. If "
        "the app clearly needs no login at all, set enabled=false.\n\n"
        f"Return JSON matching this schema:\n{schema_text(AuthSchema)}\n\n"
        f"DESIGN:\n{design.model_dump_json(indent=2)}"
    )
    return run_stage("auth", prompt, AuthSchema)


def generate_api(design: SystemDesign, database: DatabaseSchema) -> APISchema:
    prompt = (
        "You are the API-SCHEMA stage. Design REST endpoints for the app. For "
        "each entity table include the CRUD endpoints it needs. EVERY request and "
        "response field MUST correspond to a column in the database below, so the "
        "API and database agree. Use snake_case; set each endpoint's 'entity' to "
        "the table name it serves. Set requires_auth and allowed_roles to match "
        "the access rules.\n\n"
        f"Return JSON matching this schema:\n{schema_text(APISchema)}\n\n"
        f"DESIGN:\n{design.model_dump_json(indent=2)}\n\n"
        f"DATABASE (the source of truth for fields/columns):\n"
        f"{database.model_dump_json(indent=2)}"
    )
    return run_stage("api", prompt, APISchema)


def generate_ui(design: SystemDesign, api: APISchema) -> UISchema:
    prompt = (
        "You are the UI-SCHEMA stage. Design the pages and their components. Every "
        "data-bound component should set 'entity' to a table name (snake_case "
        "plural) and show fields that exist in the API below. Set requires_auth "
        "and allowed_roles per page to match the access rules. Buttons and text "
        "components may use the 'label' field for their display text.\n\n"
        f"Return JSON matching this schema:\n{schema_text(UISchema)}\n\n"
        f"DESIGN:\n{design.model_dump_json(indent=2)}\n\n"
        f"API (endpoints and fields available):\n{api.model_dump_json(indent=2)}"
    )
    return run_stage("ui", prompt, UISchema)


def generate_business_logic(design: SystemDesign, auth: AuthSchema) -> BusinessLogic:
    prompt = (
        "You are the BUSINESS-LOGIC stage. Express the enforceable rules: "
        "role-based access (e.g. analytics is admin-only), plan gating for premium "
        "features, and ownership rules. List the plans the app offers. EVERY role "
        "you reference MUST exist in the auth schema below; for plan_gating rules, "
        "'plan' must be one of the plans you list.\n\n"
        f"Return JSON matching this schema:\n{schema_text(BusinessLogic)}\n\n"
        f"DESIGN:\n{design.model_dump_json(indent=2)}\n\n"
        f"AUTH (roles you must reference correctly):\n{auth.model_dump_json(indent=2)}"
    )
    return run_stage("business_logic", prompt, BusinessLogic)
