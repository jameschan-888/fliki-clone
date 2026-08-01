"""rev35 阶段 2 P0.7: render related HTTP endpoints.

- GET  /render.latest          latest + last-success render job for a playback_id (authed)
- GET  /render-jobs            list render_jobs with pagination + user_id isolation
- GET  /render-jobs/{job_id}   detail by id (cross-user -> 404 防枚举)
- POST /render.create          enqueue a render job (authed)
- GET  /render/{filename}      serve output file with user_id check (authed)
- POST /render.cancel          cancel a queued/processing job + terminate process tree

Tests access render_create / render_cancel / RenderCreateBody / RenderCancelBody via main.* -
main.py re-exports them by import-from.
"""
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse

from config import config
from db.connection import get_db
from models.render import RenderCancelBody, RenderCreateBody
import main  # used at call time so test patches on main.terminate_process_tree apply
from workers.render_manager import (
    ACTIVE_RENDER_LOCK,
    ACTIVE_RENDER_PROCESSES,
    mark_render_cancelled,
    run_render_job,
    terminate_process_tree,
)

router = APIRouter(tags=["render"])


@router.get("/render.latest")
def render_latest(playback_id: str, request: Request = None):
    """Latest + last-success render job for a playback_id; authed user only."""
    from auth_router import get_user_id_from_request as _uid

    empty = {"renderRecent": None, "renderSuccess": None}
    user_id = _uid(request)
    if not user_id:
        return empty

    con = get_db()
    try:
        recent = con.execute(
            "SELECT * FROM render_jobs WHERE playback_id=? AND user_id=? "
            "ORDER BY created_at DESC LIMIT 1",
            (playback_id, user_id),
        ).fetchone()
        success = con.execute(
            "SELECT * FROM render_jobs WHERE playback_id=? AND user_id=? AND status='success' "
            "ORDER BY created_at DESC LIMIT 1",
            (playback_id, user_id),
        ).fetchone()

        def to_payload(row):
            if row is None:
                return None
            file_name = row["file"]
            return {
                "status": row["status"],
                "progress": int(row["progress"] or 0),
                "mediaGeneratedId": {"file": file_name} if file_name else None,
            }

        return {"renderRecent": to_payload(recent), "renderSuccess": to_payload(success)}
    finally:
        con.close()


@router.get("/render-jobs")
def render_jobs_list(request: Request = None, page: int = 0, limit: int = 50, status: str | None = None):
    """List render_jobs with backward-compatible pagination + user_id isolation.

    ?page=0 or no page  -> plain list (legacy / frontend callers)
    ?page>=1            -> {items, total, page, limit, has_more} wrapper
    """
    from auth_router import get_user_id_from_request as _uid
    user_id = _uid(request)
    if not user_id:
        return [] if (not page or page <= 0) else {"items": [], "total": 0, "page": int(page), "limit": max(1, min(int(limit or 50), 100)), "has_more": False}
    capped_limit = max(1, min(int(limit or 50), 100))
    where = " WHERE user_id = ?"
    params = [user_id]
    if status:
        where = where + " AND status = ?"
        params.append(status)
    con = None
    try:
        con = get_db()
        if not page or page <= 0:
            rows = con.execute(
                "SELECT * FROM render_jobs" + where + " ORDER BY created_at DESC LIMIT ?",
                params + [capped_limit],
            ).fetchall()
            return [dict(row) for row in rows]
        page_n = int(page)
        total = int(con.execute(
            "SELECT count(*) FROM render_jobs" + where, params
        ).fetchone()[0] or 0)
        offset = (page_n - 1) * capped_limit
        rows = con.execute(
            "SELECT * FROM render_jobs" + where + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [capped_limit, offset],
        ).fetchall()
        items = [dict(row) for row in rows]
        return {
            "items": items,
            "total": total,
            "page": page_n,
            "limit": capped_limit,
            "has_more": (offset + len(items)) < total,
        }
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass


@router.get("/render-jobs/{job_id}")
def render_job_detail(job_id: str, request: Request = None):
    """rev24 阶段 C P2-A: 按 job_id 查详情, 跨用户 404 (防枚举)."""
    user_id = None
    if request is not None:
        try:
            from auth_router import get_user_id_from_request as _g
            user_id = _g(request)
        except Exception:
            pass
    conn = get_db()
    try:
        job = conn.execute(
            "SELECT * FROM render_jobs WHERE _id=?",
            (job_id,),
        ).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="Render job not found")
        if job["user_id"] is not None and user_id != job["user_id"]:
            raise HTTPException(status_code=404, detail="Render job not found")
        return dict(job)
    finally:
        conn.close()


@router.post("/render.create")
def render_create(body: RenderCreateBody, background_tasks: BackgroundTasks, request: Request = None):
    """POST /render.create: enqueue a render job, spawn run_render_job via background task.

    user_id (optional) is bound from JWT; playback_id and config come from body.
    """
    job_id = uuid.uuid4().hex[:24]
    user_id = None
    if request is not None:
        try:
            from auth_router import get_user_id_from_request as _g
            user_id = _g(request)
        except Exception:
            pass
    conn = get_db()
    conn.execute(
        "INSERT INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, user_id, created_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (job_id, body.playback_id, "queued", 0,
         body.resolution, body.extension, body.renderer, body.engine, user_id,
         time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
    )
    conn.commit()
    conn.close()
    props_path = Path(body.props_path) if body.props_path else (Path(config["DATA_DIR"]) / "props" / (body.playback_id + ".json"))
    props_path.parent.mkdir(parents=True, exist_ok=True)
    if not props_path.exists():
        props_path.write_text("{}", encoding="utf-8")
    background_tasks.add_task(run_render_job, job_id, str(props_path), body.resolution, body.extension, body.engine, body.renderer)
    return {"jobId": job_id, "status": "queued"}


@router.get("/render/{filename}")
def render_video(filename: str, request: Request = None):
    """rev24 阶段 C P2-A: 鉴权 render 视频流, 跨用户/匿名 404 防枚举."""
    user_id = None
    if request is not None:
        try:
            from auth_router import get_user_id_from_request as _g
            user_id = _g(request)
        except Exception:
            pass
    if not user_id:
        raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "missing/invalid token", "hint": "/auth/login 或 /auth/register"})
    conn = get_db()
    try:
        job = conn.execute(
            "SELECT user_id FROM render_jobs WHERE file=?",
            (filename,),
        ).fetchone()
        if not job or job["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Render file not found")
        file_path = Path(config["OUTPUT_DIR"]) / filename
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Render file not found")
        return FileResponse(str(file_path))
    finally:
        conn.close()


@router.post("/render.cancel")
def render_cancel(body: RenderCancelBody, request: Request = None):
    """POST /render.cancel: cancel a queued/processing job; terminate process tree if registered."""
    user_id = None
    if request is not None:
        try:
            from auth_router import get_user_id_from_request as _g
            user_id = _g(request)
        except Exception:
            pass
    conn = get_db()
    job = conn.execute(
        "SELECT status, user_id FROM render_jobs WHERE _id=?",
        (body.job_id,),
    ).fetchone()
    if not job:
        conn.close()
        raise HTTPException(status_code=404, detail="Render job not found")
    if job["user_id"] is not None and user_id != job["user_id"]:
        conn.close()
        raise HTTPException(status_code=404, detail="Render job not found")
    cancelled = mark_render_cancelled(conn, body.job_id)
    conn.close()
    if not cancelled:
        return {
            "jobId": body.job_id,
            "status": job["status"],
            "cancelled": False,
            "terminated": False,
        }

    with ACTIVE_RENDER_LOCK:
        worker_process = ACTIVE_RENDER_PROCESSES.get(body.job_id)
    terminated = main.terminate_process_tree(worker_process) if worker_process else False
    return {
        "jobId": body.job_id,
        "status": "cancelled",
        "cancelled": True,
        "terminated": terminated,
    }
