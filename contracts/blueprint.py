"""The final, assembled output of the whole pipeline.

An ``AppBlueprint`` bundles the five layers (ui, api, database, auth,
business_logic) under one app identity, plus the assumptions and warnings
gathered along the way. This is the JSON the system hands back -- and the exact
input the runtime executes.
"""

from pydantic import Field

from contracts.api import APISchema
from contracts.auth import AuthSchema
from contracts.business import BusinessLogic
from contracts.common import StrictModel
from contracts.database import DatabaseSchema
from contracts.ui import UISchema


class AppBlueprint(StrictModel):
    app_name: str = Field(..., description="The app's name.")
    app_type: str = Field(..., description="The app's category.")
    ui: UISchema = Field(..., description="Pages, components, layouts.")
    api: APISchema = Field(..., description="Endpoints, methods, validation.")
    database: DatabaseSchema = Field(..., description="Tables, columns, relations.")
    auth: AuthSchema = Field(..., description="Roles and permissions.")
    business_logic: BusinessLogic = Field(..., description="Enforceable business rules.")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions surfaced anywhere in the pipeline.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues, e.g. conflicts that were auto-resolved.",
    )
