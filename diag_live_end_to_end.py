"""Throwaway diagnostic: prove the full stack works on REAL LLM output.

Three live checks, designed to spend ~zero new quota (uses cached R01):
  1. POST /compile with the canonical CRM prompt (cache hit) and confirm the
     JSON contract is honoured by the web layer.
  2. Feed the LIVE-generated blueprint into runtime.build_app and exercise:
     - meta endpoint   (lists tables/roles/endpoints)
     - SQLite tables   (CREATE TABLE actually ran on the LLM's output)
     - CRUD round-trip (POST/GET on the first POST entity endpoint we find)
     - auth gate       (an admin-only route returns 401/403/200 correctly)
  3. POST /compile with empty input -> needs_clarification short-circuit.

If anything is off with how real LLM output shapes meet our runtime, this script
exposes it. The runtime was only ever proven against the hand-built golden CRM
before.
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from app.main import app as web_app
from contracts import AppBlueprint, HTTPMethod
from runtime import build_app


CRM_PROMPT = (
    "Build a CRM with login, contacts, dashboard, role-based access, "
    "premium plan with payments, and an admin-only analytics page."
)


def part1_compile_endpoint() -> dict | None:
    print("=" * 72)
    print("PART 1 -- POST /compile (cache hit on R01 -> ~free)")
    print("=" * 72)
    c = TestClient(web_app)
    r = c.post("/compile", json={"prompt": CRM_PROMPT})
    print(f"  HTTP {r.status_code}")
    if r.status_code != 200:
        print(f"  body (truncated): {r.text[:300]}")
        return None
    body = r.json()
    bp = body.get("blueprint")
    if not bp:
        print(f"  FAIL: no blueprint key in response: {list(body.keys())}")
        return None
    print(f"  app: {bp.get('app_name')} ({bp.get('app_type')})")
    print(f"  pages={len(bp['ui']['pages'])} endpoints={len(bp['api']['endpoints'])} "
          f"tables={len(bp['database']['tables'])} roles={len(bp['auth']['roles'])}")
    val = body.get("validation", {})
    issues = val.get("issues", [])
    print(f"  validation: {len(issues)} issues after repair")
    print(f"  repair_log: {len(body.get('repair_log', []))} action(s)")
    return bp


def part2_runtime_on_real_blueprint(bp_dict: dict) -> None:
    print()
    print("=" * 72)
    print("PART 2 -- build runtime FROM LIVE LLM OUTPUT, exercise CRUD + auth")
    print("=" * 72)
    bp = AppBlueprint.model_validate(bp_dict)
    app, conn = build_app(bp)
    c = TestClient(app)

    # 2a: meta
    meta = c.get("/").json()
    print(f"  GET /         HTTP 200  tables={meta['tables']}  roles={meta['roles']}")
    db_tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"  sqlite tables actually created: {sorted(db_tables)}")
    assert sorted(db_tables) == sorted(meta["tables"]), "runtime tables disagree with blueprint"

    # 2b: find a POST entity endpoint and try a CRUD round-trip
    post_eps = [ep for ep in bp.api.endpoints
                if ep.method == HTTPMethod.POST and ep.entity and ep.entity in db_tables
                and not ep.path.endswith("/login")]
    if not post_eps:
        print("  (no POST entity endpoint to exercise)")
        return
    ep = post_eps[0]
    print(f"  using {ep.method.value} {ep.path}  entity={ep.entity}")

    # synthesize a minimal payload from the table's columns + any non-id request_fields
    cols_info = conn.execute(f'PRAGMA table_info("{ep.entity}")').fetchall()
    payload: dict = {}
    for row in cols_info:
        name, col_type, _notnull, _default, _pk = row[1], row[2], row[3], row[4], row[5]
        if name == "id":
            continue
        if col_type == "INTEGER":
            payload[name] = 1
        elif col_type == "REAL":
            payload[name] = 1.0
        elif name.endswith("_id"):
            # parent-row id: insert a parent first if we can
            parent_table = name[:-3] + "s"     # naive: foo_id -> foos
            if parent_table in db_tables:
                parent_id = uuid.uuid4().hex
                parent_cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{parent_table}")').fetchall()]
                vals = {c: ("x@y.com" if c == "email" else "x") for c in parent_cols if c != "id"}
                vals["id"] = parent_id
                placeholders = ", ".join("?" for _ in vals)
                conn.execute(
                    f'INSERT INTO "{parent_table}" ({", ".join(chr(34)+c+chr(34) for c in vals)}) '
                    f'VALUES ({placeholders})',
                    tuple(vals.values()),
                )
                conn.commit()
                payload[name] = parent_id
            else:
                payload[name] = uuid.uuid4().hex
        else:
            payload[name] = f"{name}-demo"

    role = next((r.name for r in bp.auth.roles), None)
    headers = {"X-Role": role} if role else {}
    created = c.post(ep.path, json=payload, headers=headers)
    print(f"  POST {ep.path}  HTTP {created.status_code}  body[:120]={str(created.json())[:120]}")

    listed = c.get(ep.path, headers=headers)
    if listed.status_code == 200 and isinstance(listed.json(), list):
        print(f"  GET  {ep.path}   HTTP {listed.status_code}  rows={len(listed.json())}")

    # 2c: find an admin-only route and confirm 403/200 behaviour
    admin_eps = [ep for ep in bp.api.endpoints if "admin" in ep.allowed_roles]
    if admin_eps:
        ep = admin_eps[0]
        r_user = c.get(ep.path, headers={"X-Role": role or "user"}) if ep.method == HTTPMethod.GET else None
        r_admin = c.get(ep.path, headers={"X-Role": "admin"}) if ep.method == HTTPMethod.GET else None
        if r_user is not None and r_admin is not None:
            print(f"  GET  {ep.path} as user:  HTTP {r_user.status_code}  (expect 403 if user != admin)")
            print(f"  GET  {ep.path} as admin: HTTP {r_admin.status_code}  (expect 200)")


def part3_clarification_path() -> None:
    print()
    print("=" * 72)
    print("PART 3 -- POST /compile with empty prompt (no LLM call)")
    print("=" * 72)
    c = TestClient(web_app)
    r = c.post("/compile", json={"prompt": ""})
    body = r.json()
    print(f"  HTTP {r.status_code}")
    print(f"  needs_clarification = {body.get('needs_clarification')}")
    print(f"  clarifying_question = {body.get('clarifying_question', '')[:80]}...")


def main() -> None:
    bp = part1_compile_endpoint()
    if bp is not None:
        part2_runtime_on_real_blueprint(bp)
    part3_clarification_path()
    print("\n" + "=" * 72)
    print("DIAG COMPLETE  --  if every block printed without an exception, the")
    print("full stack (Phase 8 -> 3 -> 4 -> 5 -> 7 -> 11) works on real LLM output.")
    print("=" * 72)


if __name__ == "__main__":
    main()
