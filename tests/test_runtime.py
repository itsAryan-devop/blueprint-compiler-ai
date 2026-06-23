"""Unit tests for the Phase 7 runtime (no API calls)."""

from fastapi.testclient import TestClient

from demo_contracts import build_crm_blueprint
from runtime import build_app, create_table_sql


def test_create_table_sql_includes_pk_unique_and_fk():
    bp = build_crm_blueprint()
    users = next(t for t in bp.database.tables if t.name == "users")
    sql = create_table_sql(users)
    assert "PRIMARY KEY" in sql and "UNIQUE" in sql

    contacts = next(t for t in bp.database.tables if t.name == "contacts")
    sql = create_table_sql(contacts)
    assert "FOREIGN KEY" in sql and 'REFERENCES "users"' in sql


def test_root_endpoint_lists_everything():
    app, _ = build_app(build_crm_blueprint())
    body = TestClient(app).get("/").json()
    assert body["app"] == "CRM App"
    assert "contacts" in body["tables"] and "users" in body["tables"]
    assert sorted(body["roles"]) == ["admin", "user"]


def test_crud_round_trip_against_real_sqlite():
    app, _ = build_app(build_crm_blueprint())
    # Insert the user first to satisfy the FK contacts.owner_id -> users.id
    app.state.db.execute(
        'INSERT INTO "users" (id, email, password_hash, role, plan) VALUES (?,?,?,?,?)',
        ("u1", "ada@x.com", "hashed", "user", "free"),
    )
    app.state.db.commit()
    client = TestClient(app)
    r = client.post(
        "/contacts",
        json={"owner_id": "u1", "name": "Ada", "email": "ada@x.com"},
        headers={"X-Role": "user"},
    )
    assert r.status_code == 201
    listed = client.get("/contacts", headers={"X-Role": "user"}).json()
    assert len(listed) == 1 and listed[0]["name"] == "Ada"


def test_auth_enforcement_on_admin_only_endpoint():
    app, _ = build_app(build_crm_blueprint())
    client = TestClient(app)
    assert client.get("/analytics").status_code == 401
    assert client.get("/analytics", headers={"X-Role": "user"}).status_code == 403
    assert client.get("/analytics", headers={"X-Role": "admin"}).status_code == 200


def test_unknown_role_is_rejected():
    app, _ = build_app(build_crm_blueprint())
    r = TestClient(app).get("/contacts", headers={"X-Role": "ghost"})
    assert r.status_code == 401
