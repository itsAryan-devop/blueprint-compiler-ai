"""Runtime regression: handlers must work for ANY path-parameter name
(``{id}``, ``{user_id}``, ``{contact_id}``), not only ``{id}``."""

from fastapi.testclient import TestClient

from contracts import (
    APIField,
    APISchema,
    AppBlueprint,
    AuthSchema,
    BusinessLogic,
    Column,
    DatabaseSchema,
    Endpoint,
    FieldType,
    HTTPMethod,
    Page,
    Table,
    UISchema,
)
from runtime import build_app


def _blueprint_with_user_id_param() -> AppBlueprint:
    return AppBlueprint(
        app_name="X", app_type="X",
        ui=UISchema(pages=[Page(name="Home", path="/")]),
        api=APISchema(endpoints=[
            Endpoint(name="get_user", method=HTTPMethod.GET, path="/users/{user_id}",
                     entity="users"),
            Endpoint(name="create_user", method=HTTPMethod.POST, path="/users",
                     entity="users",
                     request_fields=[
                         APIField(name="email", type=FieldType.STRING),
                         APIField(name="name", type=FieldType.STRING),
                     ]),
        ]),
        database=DatabaseSchema(tables=[
            Table(name="users", columns=[
                Column(name="id", type=FieldType.UUID, primary_key=True),
                Column(name="email", type=FieldType.STRING),
                Column(name="name", type=FieldType.STRING),
            ]),
        ]),
        auth=AuthSchema(enabled=False),
        business_logic=BusinessLogic(),
    )


def test_get_one_works_with_non_id_path_param():
    app, _ = build_app(_blueprint_with_user_id_param())
    client = TestClient(app)
    created = client.post("/users", json={"email": "a@b.com", "name": "Ada"})
    assert created.status_code == 201
    user_id = created.json()["id"]

    got = client.get(f"/users/{user_id}")
    assert got.status_code == 200
    assert got.json()["email"] == "a@b.com"
