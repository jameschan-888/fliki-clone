"""C4 share links for preview and iframe embedding."""
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from db.connection import get_db


def ensure_share_table(con):
    con.execute("""
      CREATE TABLE IF NOT EXISTS share_links (
        id TEXT PRIMARY KEY,
        token TEXT UNIQUE NOT NULL,
        draft_id TEXT NOT NULL,
        owner_user_id TEXT NOT NULL,
        visibility TEXT NOT NULL DEFAULT 'unlisted',
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL,
        revoked_at TEXT
      )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_share_token ON share_links(token)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_share_owner ON share_links(owner_user_id, created_at DESC)")
    con.commit()


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create_router(get_db=get_db):
    router = APIRouter(prefix="", tags=["sharing"])
    from auth_router import get_user_id_from_request
    from workflow_drafts import draft_payload

    def actor(request):
        value = get_user_id_from_request(request)
        if not value:
            raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "需要登录"})
        return value

    @router.post("/workflow-drafts/{draft_id}/share")
    def create_share(draft_id: str, request: Request):
        owner = actor(request)
        with get_db() as con:
            ensure_share_table(con)
            draft = con.execute("SELECT id, user_id FROM workflow_drafts WHERE id=?", (draft_id,)).fetchone()
            if not draft or draft[1] != owner:
                raise HTTPException(status_code=404, detail={"error_code": "DRAFT_NOT_FOUND"})
            existing = con.execute("SELECT token, visibility FROM share_links WHERE draft_id=? AND owner_user_id=? AND status='active'", (draft_id, owner)).fetchone()
            if existing:
                token, visibility = existing[0], existing[1]
            else:
                token, visibility = secrets.token_urlsafe(32), "unlisted"
                con.execute("INSERT INTO share_links VALUES (?, ?, ?, ?, ?, 'active', ?, NULL)", (uuid.uuid4().hex, token, draft_id, owner, visibility, _now()))
                con.commit()
        return {"token": token, "draft_id": draft_id, "visibility": visibility, "url": "/share.html?token=" + token, "embed_url": "/share.html?token=" + token}

    @router.delete("/workflow-drafts/{draft_id}/share")
    def revoke_share(draft_id: str, request: Request):
        owner = actor(request)
        with get_db() as con:
            ensure_share_table(con)
            changed = con.execute("UPDATE share_links SET status='revoked', revoked_at=? WHERE draft_id=? AND owner_user_id=? AND status='active'", (_now(), draft_id, owner)).rowcount
            con.commit()
        return {"revoked": bool(changed)}

    @router.get("/share/{token}")
    def public_share(token: str):
        with get_db() as con:
            ensure_share_table(con)
            link = con.execute("SELECT draft_id FROM share_links WHERE token=? AND status='active'", (token,)).fetchone()
            if not link:
                raise HTTPException(status_code=404, detail={"error_code": "SHARE_NOT_FOUND"})
            return {"share": {"token": token, "draft": draft_payload(con, link[0])}}

    @router.get("/share/{token}/embed")
    def embed_share(token: str):
        result = public_share(token)
        result["embed"] = {"allow": "fullscreen; autoplay", "type": "video-preview"}
        return result

    return router
