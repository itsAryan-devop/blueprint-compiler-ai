"""Output layer 3 of 5: the UI schema (pages, components, layouts).

Every data-bound component names the entity it shows and the fields it displays,
so the UI can be checked against the API and database: a 'phone' field on a form
is only valid if the API accepts it and a column stores it.
"""

from pydantic import Field

from contracts.common import ComponentType, StrictModel


class UIField(StrictModel):
    name: str = Field(..., description="The data field this element is bound to, in snake_case, e.g. 'email'.")
    label: str = Field(..., description="Human-readable label, e.g. 'Email address'.")
    component: ComponentType = Field(default=ComponentType.INPUT, description="How this field is rendered.")


class Component(StrictModel):
    type: ComponentType = Field(..., description="The kind of UI component.")
    name: str = Field(..., description="A short identifier or title, e.g. 'ContactsTable'.")
    label: str = Field(
        default="",
        description="Display text for components that carry text, e.g. a button's caption or a heading.",
    )
    entity: str | None = Field(
        default=None,
        description="The entity this component displays or edits, e.g. 'contacts'. Null for static or auth components.",
    )
    fields: list[UIField] = Field(
        default_factory=list,
        description="The data fields shown or edited by this component.",
    )


class Page(StrictModel):
    name: str = Field(..., description="Page name, e.g. 'Contacts'.")
    path: str = Field(..., description="Route path, e.g. '/contacts'.")
    description: str = Field(default="", description="What the page is for.")
    requires_auth: bool = Field(default=False, description="True if the user must be logged in to view it.")
    allowed_roles: list[str] = Field(
        default_factory=list,
        description="Roles allowed to view the page. Empty = any authenticated user.",
    )
    components: list[Component] = Field(default_factory=list, description="Components placed on this page.")


class UISchema(StrictModel):
    pages: list[Page] = Field(..., min_length=1, description="All pages or screens in the app.")
