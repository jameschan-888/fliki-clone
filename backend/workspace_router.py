"""C2 workspace membership and role boundaries."""
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from db.connection import get_db


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def ensure_workspace_tables(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS workspaces (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      owner_user_id TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS workspace_members (
      workspace_id TEXT NOT NULL,
      user_id TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'member',
      created_at TEXT NOT NULL,
      PRIMARY KEY (workspace_id, user_id),
      FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
    """)
    users = con.execute("SELECT id FROM users").fetchall()
    for row in users:
        existing = con.execute("SELECT 1 FROM workspace_members WHERE user_id=? LIMIT 1", (row[0],)).fetchone()
        if existing:
            continue
        workspace_id = uuid.uuid4().hex
        now = _now()
        con.execute("INSERT INTO workspaces VALUES (?, ?, ?, ?, ?)", (workspace_id, "My Workspace", row[0], now, now))
        con.execute("INSERT INTO workspace_members VALUES (?, ?, 'owner', ?)", (workspace_id, row[0], now))
    con.commit()


class WorkspaceBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class MemberBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: str = Field(default="member", pattern="^(member|admin)$")


def create_router(get_db=get_db):
    router = APIRouter(prefix="/workspaces", tags=["workspaces"])
    from auth_router import get_user_id_from_request

    def user_id(request):
        value = get_user_id_from_request(request)
        if not value:
            raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "需要登录"})
        return value

    def membership(con, workspace_id, actor_id):
        row = con.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?", (workspace_id, actor_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error_code": "WORKSPACE_NOT_FOUND"})
        return row[0]

    @router.get("")
    def list_workspaces(request: Request):
        actor_id = user_id(request)
        with get_db() as con:
            ensure_workspace_tables(con)
            rows = con.execute("SELECT w.id, w.name, w.owner_user_id, w.created_at, wm.role FROM workspaces w JOIN workspace_members wm ON wm.workspace_id=w.id WHERE wm.user_id=? ORDER BY w.created_at", (actor_id,)).fetchall()
        return {"workspaces": [dict(row) for row in rows]}

    @router.post("")
    def create_workspace(body: WorkspaceBody, request: Request):
        actor_id = user_id(request)
        workspace_id, now = uuid.uuid4().hex, _now()
        with get_db() as con:
            ensure_workspace_tables(con)
            con.execute("INSERT INTO workspaces VALUES (?, ?, ?, ?, ?)", (workspace_id, body.name.strip(), actor_id, now, now))
            con.execute("INSERT INTO workspace_members VALUES (?, ?, 'owner', ?)", (workspace_id, actor_id, now))
            con.commit()
        return {"id": workspace_id, "name": body.name.strip(), "role": "owner"}

    @router.post("/{workspace_id}/members")
    def add_member(workspace_id: str, body: MemberBody, request: Request):
        actor_id = user_id(request)
        with get_db() as con:
            role = membership(con, workspace_id, actor_id)
            if role not in ("owner", "admin"):
                raise HTTPException(status_code=403, detail={"error_code": "WORKSPACE_ADMIN_ONLY"})
            if not con.execute("SELECT 1 FROM users WHERE id=?", (body.user_id,)).fetchone():
                raise HTTPException(status_code=404, detail={"error_code": "USER_NOT_FOUND"})
            try:
                con.execute("INSERT INTO workspace_members VALUES (?, ?, ?, ?)", (workspace_id, body.user_id, body.role, _now()))
                con.commit()
            except Exception:
                raise HTTPException(status_code=409, detail={"error_code": "MEMBER_EXISTS"})
        return {"workspace_id": workspace_id, "user_id": body.user_id, "role": body.role}

    @router.get("/{workspace_id}/members")
    def list_members(workspace_id: str, request: Request):
        actor_id = user_id(request)
        with get_db() as con:
            membership(con, workspace_id, actor_id)
            rows = con.execute("SELECT wm.user_id, u.email, wm.role, wm.created_at FROM workspace_members wm JOIN users u ON u.id=wm.user_id WHERE wm.workspace_id=? ORDER BY wm.created_at", (workspace_id,)).fetchall()
        return {"members": [dict(row) for row in rows]}

    return router
