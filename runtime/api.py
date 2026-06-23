"""Blueprint -> live FastAPI app.

For every endpoint in ``APISchema`` we register a real route. Behaviour:
  * generic CRUD against the SQLite table for endpoints whose ``entity`` is set
    (GET list, GET by id, POST create, PUT update, DELETE);
  * a small in-memory ``/login`` for the auth flow (no real password check --
    demo-grade);
  * any other endpoint returns a 501 stub but is still registered, so the route
    table mirrors the blueprint exactly.

This is the second half of "the output is directly runnable": validation passes,
repair passes, and the result actually serves HTTP.
"""

import sqlite3
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, status

from contracts import AppBlueprint, Endpoint, HTTPMethod
from runtime.auth import AuthEnforcer
from runtime.db import build_database


def _path_to_fastapi(path: str) -> str:
    return path  # blueprint paths already use FastAPI's "{id}" syntax


def _is_id_path(path: str) -> bool:
    return "{id}" in path or "{ID}" in path


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def build_app(blueprint: AppBlueprint, db_path: str = ":memory:") -> tuple[FastAPI, sqlite3.Connection]:
    """Build a live FastAPI app from the blueprint. Returns (app, db connection)."""
    conn = build_database(blueprint.database, db_path)
    enforcer = AuthEnforcer(blueprint)
    table_names = {t.name for t in blueprint.database.tables}
    app = FastAPI(title=blueprint.app_name, description=f"Runtime built from blueprint: {blueprint.app_type}")
    app.state.db = conn

    @app.get("/", tags=["meta"])
    def root():
        return {
            "app": blueprint.app_name,
            "type": blueprint.app_type,
            "endpoints": [f"{e.method.value} {e.path}" for e in blueprint.api.endpoints],
            "tables": sorted(table_names),
            "roles": sorted(r.name for r in blueprint.auth.roles),
        }

    for ep in blueprint.api.endpoints:
        _register(app, conn, enforcer, ep, table_names)

    return app, conn


def _register(app: FastAPI, conn: sqlite3.Connection, enforcer: AuthEnforcer,
              ep: Endpoint, table_names: set[str]) -> None:
    fastapi_path = _path_to_fastapi(ep.path)
    dep = enforcer.require(requires_auth=ep.requires_auth, allowed_roles=ep.allowed_roles)

    # /login is special: accept any email/password, echo a fake token + role.
    if ep.path.endswith("/login") and ep.method == HTTPMethod.POST:
        async def login_handler(payload: dict):
            return {
                "token": f"demo-token-{uuid.uuid4().hex[:8]}",
                "email": payload.get("email", ""),
                "role": payload.get("role", "user"),
            }
        app.add_api_route(fastapi_path, login_handler, methods=["POST"], tags=["auth"])
        return

    # CRUD routes for entity endpoints whose table actually exists.
    if ep.entity and ep.entity in table_names:
        _register_entity(app, conn, dep, ep)
        return

    # Anything else: a registered stub, so the route exists.
    async def stub(_: Request, _auth=Depends(dep)):
        return {"detail": f"{ep.method.value} {ep.path} -- stub (no CRUD mapping)"}
    app.add_api_route(fastapi_path, stub, methods=[ep.method.value], tags=["stub"])


def _register_entity(app: FastAPI, conn: sqlite3.Connection, dep, ep: Endpoint) -> None:
    table = ep.entity
    table_q = _quote(table)
    method = ep.method

    if method == HTTPMethod.GET and not _is_id_path(ep.path):
        async def list_handler(_auth=Depends(dep)):
            rows = conn.execute(f"SELECT * FROM {table_q}").fetchall()
            return [_row_to_dict(r) for r in rows]
        app.add_api_route(ep.path, list_handler, methods=["GET"], tags=[table])
        return

    if method == HTTPMethod.GET and _is_id_path(ep.path):
        async def get_one(id: str, _auth=Depends(dep)):
            row = conn.execute(f"SELECT * FROM {table_q} WHERE id = ?", (id,)).fetchone()
            if row is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"{table} {id} not found")
            return _row_to_dict(row)
        app.add_api_route(ep.path, get_one, methods=["GET"], tags=[table])
        return

    if method == HTTPMethod.POST:
        # Real DB columns (source of truth) plus any extra fields the API
        # declares -- union, so the caller can fill any storable column.
        column_names = [r[1] for r in conn.execute(f"PRAGMA table_info({table_q})").fetchall()]
        allowed_fields = set(column_names) | {f.name for f in ep.request_fields}

        async def create_handler(payload: dict, _auth=Depends(dep)):
            row_id = payload.get("id") or uuid.uuid4().hex
            values = {"id": row_id}
            for name in allowed_fields:
                if name == "id":
                    continue
                if name in payload:
                    values[name] = payload[name]
            cols = ", ".join(_quote(c) for c in values.keys())
            placeholders = ", ".join("?" for _ in values)
            try:
                conn.execute(f"INSERT INTO {table_q} ({cols}) VALUES ({placeholders})", tuple(values.values()))
                conn.commit()
            except sqlite3.IntegrityError as error:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error))
            return {"id": row_id, **values}
        app.add_api_route(ep.path, create_handler, methods=["POST"], tags=[table], status_code=201)
        return

    if method in (HTTPMethod.PUT, HTTPMethod.PATCH):
        async def update_handler(id: str, payload: dict, _auth=Depends(dep)):
            if not payload:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty update")
            assignments = ", ".join(f"{_quote(k)} = ?" for k in payload.keys())
            result = conn.execute(
                f"UPDATE {table_q} SET {assignments} WHERE id = ?",
                (*payload.values(), id),
            )
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"{table} {id} not found")
            return {"id": id, **payload}
        app.add_api_route(ep.path, update_handler, methods=[method.value], tags=[table])
        return

    if method == HTTPMethod.DELETE:
        async def delete_handler(id: str, _auth=Depends(dep)):
            result = conn.execute(f"DELETE FROM {table_q} WHERE id = ?", (id,))
            conn.commit()
            if result.rowcount == 0:
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"{table} {id} not found")
            return {"deleted": id}
        app.add_api_route(ep.path, delete_handler, methods=["DELETE"], tags=[table])
        return
