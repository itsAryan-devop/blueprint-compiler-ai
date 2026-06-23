"""Shared building blocks for every contract: a strict base model and the
controlled vocabularies (enums) reused across layers.

Reusing ONE ``FieldType`` across entities, database columns, and API fields is a
deliberate choice: it makes cross-layer consistency checkable later, because an
API field's type can be compared directly to its database column's type.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Base class for all contracts.

    ``extra="forbid"`` makes Pydantic reject any field that is not declared in
    the contract. That one setting is what turns "the LLM hallucinated an extra
    key" from a silent bug into a caught, repairable error.
    """

    model_config = ConfigDict(extra="forbid")


class FieldType(str, Enum):
    """Allowed data types for a piece of data, shared by entities, database
    columns, and API fields so the three layers speak the same language."""

    STRING = "string"
    TEXT = "text"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    UUID = "uuid"
    JSON = "json"


class HTTPMethod(str, Enum):
    """Allowed HTTP methods for API endpoints."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class RelationshipType(str, Enum):
    """How two entities relate to each other (the four cardinalities)."""

    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class ComponentType(str, Enum):
    """The kinds of UI components a page can contain.

    Kept compact but covers the common bindings the model picks for typical app
    blueprints. SELECT/CHECKBOX/RADIO/TEXTAREA are added because the eval (Phase
    9) caught the LLM emitting them on real prompts -- they are legitimate UI
    bindings, not hallucinations.
    """

    NAVBAR = "navbar"
    TABLE = "table"
    FORM = "form"
    INPUT = "input"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    BUTTON = "button"
    CHART = "chart"
    LIST = "list"
    CARD = "card"
    MODAL = "modal"
    IMAGE = "image"
    LINK = "link"
    TEXT = "text"
