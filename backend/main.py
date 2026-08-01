"""Fliki 还原后端 - FastAPI 主入口"""
import hashlib, json, os, platform, re, signal, sqlite3, threading, time, uuid, subprocess
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from secure_middleware import install_security_middleware
from request_context import install_request_context

from errors import make_error_response, normalize_http_exception_detail, DEFAULT_ERROR_CODE_BY_STATUS, ERR_VALIDATION_ERROR, ERR_INTERNAL_ERROR, ERR_UNKNOWN
from config import config, DEFAULT_PROVIDERS
from db.connection import get_db, init_db
from routers.startup import router as startup_router, run_startup_diagnostic_background
from routers.alerts import router as alerts_router
from routers.analytics import router as analytics_router
from models.render import RenderCreateBody, RenderCancelBody  # re-exported for tests
from workers.render_manager import (  # re-exported for tests
    ACTIVE_RENDER_LOCK, ACTIVE_RENDER_PROCESSES, WORKER_PROGRESS_PATTERN,
    apply_worker_progress, expire_render_process, mark_render_cancelled,
    run_render_job, terminate_process_tree,
)
from routers.render import (  # re-exported for tests + workflow_pipeline / autoedit
    router as render_router, render_create, render_cancel,
    render_latest, render_jobs_list, render_job_detail, render_video,
)
from workflow_drafts import create_router as create_workflow_drafts_router
from provider_config import create_router as create_provider_config_router, seed_runtime_providers, hydrate_env_from_disk
from workflow_pipeline import create_router as create_workflow_pipeline_router
from autoedit import create_router as create_autoedit_router
from autoedit_pipeline import create_router as create_autoedit_pipeline_router
from env_check_router import create_router as create_env_check_router
from env_check import run_full_diagnostic
from voice_gallery import create_router as create_voice_gallery_router, ensure_voices
from voice_clone_router import create_router as create_voice_clone_router
from avatar_clone_router import create_router as create_avatar_clone_router
from uploads_router import create_router as create_uploads_router
from templates_router import create_router as create_templates_router
from minimax_voice_clones_router import create_router as create_minimax_voice_clones_router
from metrics_router import create_router as create_metrics_router


hydrate_env_from_disk()


# ===== P2-Hardening: 启动时校验 JWT_SECRET, prod 环境占位符直接 raise =====
try:
    from auth_router import validate_jwt_secret as _validate_jwt_secret
    _validate_jwt_secret(strict=(os.environ.get("FLIKI_ENV", "").lower() == "prod"))
    del _validate_jwt_secret
except RuntimeError as _jwt_exc:
    import sys as _sys
    print("[main] refusing to start due to insecure JWT_SECRET:", _jwt_exc, file=_sys.stderr)
    raise


# ===== App =====
app = FastAPI(title="Fliki Clone API", version="0.1.0")



install_security_middleware(app)
install_request_context(app)
# 借鉴灵剪 packages/core/errors.py：统一 LingjianError + HTTPException 响应体。
from errors import register_error_handlers  # noqa: E402
register_error_handlers(app)

# rev24 阶段 D P0: on_event 已 deprecated (FastAPI 0.110+), 改用 lifespan context manager.
# 启动逻辑等价: users 表 → init_db → seed providers → ensure voices → 后台诊断线程.
@asynccontextmanager
async def lifespan(app):
    try:
        from auth_router import ensure_users_table as _eut
        _eut()
    except Exception as e:
        print("[auth] users table init warning:", e)
    if init_db():
        print("[database] Added scene_drafts.voice compatibility column")
    connection = get_db()
    try:
        seed_runtime_providers(connection)
        ensure_voices(connection)
    finally:
        connection.close()
    run_startup_diagnostic_background()
    yield
    # shutdown: 当前无 cleanup, 留 hook 位置

app.router.lifespan_context = lifespan

app.include_router(startup_router)
app.include_router(alerts_router)
app.include_router(analytics_router)
app.include_router(render_router)
app.include_router(create_workflow_drafts_router(get_db))
app.include_router(create_provider_config_router(get_db))
VOICE_PREVIEW_DIR = Path(config["DATA_DIR"]) / "voice_previews"
VOICE_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/voice-previews", StaticFiles(directory=str(VOICE_PREVIEW_DIR)), name="voice-previews")
OUTPUT_DIR = Path(config["OUTPUT_DIR"])
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
# rev24 阶段 D P0: /outputs StaticFiles mount 保留 (兼容 autoedit 视频流),
# 但 P2-A 新增 /render/{filename} 鉴权端点供 workflow-drafts render 走 (跨用户 404).
# /outputs 安全层: 文件名 = {run_id}/{name}.mp4, run_id 是 UUID 128-bit 不可枚举,
# 跨用户需知道别人 UUID 才能访问 (industry 标准, 类似 S3 pre-signed URL).
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
UPLOAD_DIR = Path(config["DATA_DIR"]) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.include_router(create_voice_gallery_router(get_db, VOICE_PREVIEW_DIR))
app.include_router(create_voice_clone_router(get_db, VOICE_PREVIEW_DIR))
app.include_router(create_avatar_clone_router(get_db))
app.include_router(create_uploads_router())
app.include_router(create_templates_router(get_db))
app.include_router(create_minimax_voice_clones_router(get_db))
app.include_router(create_metrics_router(get_db))
@app.get("/metrics")
def metrics():
    """Prometheus-compatible metrics endpoint.

    Counters (Gauge-based for point-in-time):
      - fliki_render_jobs_total{status=...} render_jobs by status
      - fliki_workflow_runs_total{status=...} workflow_runs by status
      - fliki_workflow_drafts_total drafts count
      - fliki_render_queue_active semaphore active slots
      - fliki_backend_up backend liveness (always 1)
    Plus user/tenant dimensional metrics via _emit_user_metrics / _emit_tenant_metrics.
    """
    out = []
    con = None
    try:
        con = get_db()
        # render_jobs by status
        try:
            for status, cnt in con.execute(
                "SELECT status, COUNT(*) FROM render_jobs GROUP BY status"
            ).fetchall():
                out.append('fliki_render_jobs_total{status="' + str(status or "unknown") + '"} ' + str(cnt))
        except Exception as e:
            out.append("# render_jobs_total error: " + str(e))
        out.append("")

        # workflow_runs by status
        try:
            for status, cnt in con.execute(
                "SELECT status, COUNT(*) FROM workflow_runs GROUP BY status"
            ).fetchall():
                out.append('fliki_workflow_runs_total{status="' + str(status or "unknown") + '"} ' + str(cnt))
        except Exception as e:
            out.append("# workflow_runs_total error: " + str(e))
        out.append("")

        # workflow_drafts total
        drafts = _safe_count(con, "SELECT count(*) FROM workflow_drafts")
        out.append('fliki_workflow_drafts_total ' + str(drafts))
        out.append("")

        # render_queue_active (proxy: count of active render processes)
        try:
            active = len(ACTIVE_RENDER_PROCESSES) if ACTIVE_RENDER_PROCESSES is not None else 0
        except Exception:
            active = 0
        out.append('fliki_render_queue_active ' + str(active))
        out.append("")

        # backend_up
        out.append('fliki_backend_up 1')
        out.append("")

        # user dimension (P1-A)
        try:
            _emit_user_metrics(con, out)
        except Exception as e:
            out.append("# _emit_user_metrics error: " + str(e))

        # tenant dimension (D1-1)
        try:
            _emit_tenant_metrics(con, out)
        except Exception as e:
            out.append("# _emit_tenant_metrics error: " + str(e))

        body = "\n".join(out) + "\n"
        return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:
                pass











app.include_router(create_workflow_pipeline_router(get_db, render_create, RenderCreateBody))
app.include_router(create_autoedit_router(get_db, render_create, RenderCreateBody, config["MAX_UPLOAD_BYTES"]))
app.include_router(create_autoedit_pipeline_router(get_db))
app.include_router(create_env_check_router())
# rev18 stage C item #6: auth router (JWT, simple users table)
try:
    from auth_router import router as auth_router_router
except Exception as _e:
    print("[auth] router import failed:", _e)
    auth_router_router = None
if auth_router_router is not None:
    app.include_router(auth_router_router)

# rev24 阶段 D P1-B: alerts module (manager + eval)
from alerts import eval_rules, get_rules_info, MANAGER as _ALERT_MANAGER



