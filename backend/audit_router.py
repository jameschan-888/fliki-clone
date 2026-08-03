"""C1 audit trail endpoints for production accountability."""
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from db.connection import get_db


def ensure_audit_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            actor_user_id TEXT,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor_created ON audit_logs(actor_user_id, created_at DESC)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_audit_action_created ON audit_logs(action, created_at DESC)")
    con.commit()


def write_audit(con, actor_user_id, action, resource_type=None, resource_id=None, metadata=None):
    ensure_audit_table(con)
    con.execute(
        "INSERT INTO audit_logs (id, actor_user_id, action, resource_type, resource_id, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, actor_user_id, action, resource_type, resource_id, json.dumps(metadata or {}, ensure_ascii=False), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
    )
    con.commit()


def create_router(get_db=get_db):
    router = APIRouter(prefix="/audit-logs", tags=["audit"])
    from auth_router import get_user_id_from_request

    def actor(request):
        user_id = get_user_id_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "需要登录"})
        return user_id

    @router.get("/me")
    def list_my_logs(request: Request, limit: int = Query(default=50, ge=1, le=200)):
        user_id = actor(request)
        with get_db() as con:
            ensure_audit_table(con)
            rows = con.execute("SELECT id, actor_user_id, action, resource_type, resource_id, metadata_json, created_at FROM audit_logs WHERE actor_user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)).fetchall()
        return {"logs": [_serialize(row) for row in rows], "total": len(rows)}

    @router.get("")
    def list_all_logs(request: Request, limit: int = Query(default=100, ge=1, le=500), user_id: str | None = None, action: str | None = None):
        actor_id = actor(request)
        with get_db() as con:
            role = con.execute("SELECT role FROM users WHERE id=?", (actor_id,)).fetchone()
            if not role or role[0] != "admin":
                raise HTTPException(status_code=403, detail={"error_code": "ADMIN_ONLY", "message": "需要 admin 权限"})
            clauses, params = [], []
            if user_id:
                clauses.append("actor_user_id=?")
                params.append(user_id)
            if action:
                clauses.append("action=?")
                params.append(action)
            where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(limit)
            ensure_audit_table(con)
            rows = con.execute("SELECT id, actor_user_id, action, resource_type, resource_id, metadata_json, created_at FROM audit_logs" + where + " ORDER BY created_at DESC LIMIT ?", params).fetchall()
        return {"logs": [_serialize(row) for row in rows], "total": len(rows)}

    return router


def _serialize(row):
    item = dict(row)
    try:
        item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
    except (TypeError, ValueError):
        item["metadata"] = {}
        item.pop("metadata_json", None)
    return item
