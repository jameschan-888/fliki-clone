"""C5 workspace-scoped Brand Kit persistence."""
import json
import time
from fastapi import APIRouter, HTTPException, Request
from db.connection import get_db


def ensure_brand_kit_table(con):
    con.execute("""
      CREATE TABLE IF NOT EXISTS workspace_brand_kits (
        workspace_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        palette_json TEXT NOT NULL DEFAULT '[]',
        font TEXT NOT NULL DEFAULT 'Noto Sans SC',
        logo_data_url TEXT,
        watermark INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
      )
    """)
    con.commit()


def create_router(get_db):
    router = APIRouter(prefix="", tags=["brand-kit"])
    from auth_router import get_user_id_from_request

    def require_member(request, workspace_id, write=False):
        user_id = get_user_id_from_request(request)
        if not user_id:
            raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "需要登录"})
        with get_db() as con:
            row = con.execute("SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?", (workspace_id, user_id)).fetchone()
        if not row or (write and row[0] not in ("owner", "admin")):
            raise HTTPException(status_code=404 if not row else 403, detail={"error_code": "BRAND_KIT_ACCESS_DENIED"})
        return user_id

    @router.get("/workspaces/{workspace_id}/brand-kit")
    def get_brand_kit(workspace_id: str, request: Request):
        require_member(request, workspace_id)
        with get_db() as con:
            ensure_brand_kit_table(con)
            row = con.execute("SELECT workspace_id,name,palette_json,font,logo_data_url,watermark,updated_at FROM workspace_brand_kits WHERE workspace_id=?", (workspace_id,)).fetchone()
        if not row:
            return {"workspace_id": workspace_id, "name": "Default Brand", "palette": ["#5b6cff", "#48d58b", "#ffaa28", "#dc5050"], "font": "Noto Sans SC", "logo_data_url": None, "watermark": False}
        return {"workspace_id": row[0], "name": row[1], "palette": json.loads(row[2]), "font": row[3], "logo_data_url": row[4], "watermark": bool(row[5]), "updated_at": row[6]}

    @router.put("/workspaces/{workspace_id}/brand-kit")
    def put_brand_kit(workspace_id: str, body: dict, request: Request):
        require_member(request, workspace_id, write=True)
        name = str(body.get("name") or "Default Brand")[:120]
        palette = body.get("palette") or []
        if not isinstance(palette, list) or len(palette) != 4 or any(not isinstance(item, str) for item in palette):
            raise HTTPException(status_code=422, detail={"error_code": "INVALID_PALETTE"})
        font = str(body.get("font") or "Noto Sans SC")[:80]
        logo = body.get("logo_data_url")
        if logo is not None and (not isinstance(logo, str) or len(logo) > 2_000_000):
            raise HTTPException(status_code=422, detail={"error_code": "INVALID_LOGO"})
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with get_db() as con:
            ensure_brand_kit_table(con)
            con.execute("INSERT OR REPLACE INTO workspace_brand_kits VALUES (?,?,?,?,?,?,?)", (workspace_id, name, json.dumps(palette, ensure_ascii=False), font, logo, int(bool(body.get("watermark"))), now))
            con.commit()
        return get_brand_kit(workspace_id, request)

    return router
