"""Pydantic contracts — the strict shapes every pipeline stage must produce.

Defining these *first* (contract-first design) is what lets us guarantee valid
JSON, required fields, and type safety before we ever trust the LLM's output.

This package re-exports every public contract so the rest of the codebase can do
``from contracts import IntentSpec, AppBlueprint`` without reaching into submodules.
"""

from contracts.common import (
    ComponentType,
    FieldType,
    HTTPMethod,
    RelationshipType,
    StrictModel,
)
from contracts.intent import IntentSpec
from contracts.design import (
    BusinessRule,
    Entity,
    EntityField,
    Flow,
    Relationship,
    Role,
    SystemDesign,
)
from contracts.database import Column, DatabaseSchema, Table
from contracts.api import APIField, APISchema, Endpoint
from contracts.ui import Component, Page, UIField, UISchema
from contracts.auth import AuthRole, AuthSchema, Permission
from contracts.business import BusinessLogic, BusinessLogicRule, RuleType
from contracts.blueprint import AppBlueprint

__all__ = [
    # common
    "StrictModel", "FieldType", "HTTPMethod", "RelationshipType", "ComponentType",
    # intent (Stage 1)
    "IntentSpec",
    # design (Stage 2)
    "SystemDesign", "Entity", "EntityField", "Relationship", "Role", "Flow", "BusinessRule",
    # database (output layer)
    "DatabaseSchema", "Table", "Column",
    # api (output layer)
    "APISchema", "Endpoint", "APIField",
    # ui (output layer)
    "UISchema", "Page", "Component", "UIField",
    # auth (output layer)
    "AuthSchema", "AuthRole", "Permission",
    # business logic (output layer)
    "BusinessLogic", "BusinessLogicRule", "RuleType",
    # final assembled output
    "AppBlueprint",
]
