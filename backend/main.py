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

from errors import make_error_response, normalize_http_exception_detail, DEFAULT_ERROR_CODE_BY_STATUS, ERR_VALIDATION_ERROR, ERR_INTERNAL_ERROR, ERR_UNKNOWN
from config import config, DEFAULT_PROVIDERS
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

# ===== DB =====
def get_db():
    conn = sqlite3.connect(config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

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


def init_db():
    schema = Path(__file__).parent / "db" / "schema.sql"
    conn = get_db()
    try:
        conn.executescript(schema.read_text(encoding="utf-8"))
        migrated = False
        for table, col_defs in (
            ("scene_drafts", (("voice", "TEXT NOT NULL DEFAULT 'zh-CN-XiaoxiaoNeural'"),
                              ("avatar", "TEXT"),
                              ("avatar_layout", "TEXT"),
                              ("template_id", "TEXT"),
                              ("template_fields", "TEXT"),
                              ("stock_url", "TEXT"),
                              ("camera_motion", "TEXT NOT NULL DEFAULT 'zoom-in'"),
                              ("video_aspect", "TEXT NOT NULL DEFAULT '16:9'"),
                              ("video_transition_mode", "TEXT NOT NULL DEFAULT 'fade'"),
                              ("media_width", "INTEGER NOT NULL DEFAULT 1280"),
                              ("media_height", "INTEGER NOT NULL DEFAULT 720"),
                              ("subtitle_display", "TEXT"),
                              ("subtitle_spoken", "TEXT"))),
        ):
            tcols = {row["name"] for row in conn.execute("PRAGMA table_info(" + table + ")").fetchall()}
            if not tcols:
                continue
            for col, decl in col_defs:
                if col not in tcols:
                    conn.execute("ALTER TABLE " + table + " ADD COLUMN " + col + " " + decl)
                    migrated = True
        # rev24 stage C #8: multi-tenant FK
        for table in ("workflow_drafts", "workflow_runs", "render_jobs"):
            tcols = {row["name"] for row in conn.execute("PRAGMA table_info(" + table + ")").fetchall()}
            if not tcols:
                continue
            if "user_id" not in tcols:
                conn.execute("ALTER TABLE " + table + " ADD COLUMN user_id TEXT")
                migrated = True
            if "user_id" in tcols:
                # rev24 stage C #8: indexes for user_id
                for idx_sql in (
                    "CREATE INDEX IF NOT EXISTS idx_workflow_drafts_user ON workflow_drafts(user_id, updated_at DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_workflow_runs_user ON workflow_runs(user_id, created_at DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_render_jobs_user ON render_jobs(user_id, created_at DESC)",
                ):
                    pass  # placeholder; actual indexes are table-specific
                # create table-specific index only
                if table == "workflow_drafts":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_drafts_user ON workflow_drafts(user_id, updated_at DESC)")
                elif table == "workflow_runs":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_user ON workflow_runs(user_id, created_at DESC)")
                elif table == "render_jobs":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_render_jobs_user ON render_jobs(user_id, created_at DESC)")
        if migrated:
            conn.commit()
        return migrated
    finally:
        conn.close()

_startup_diagnostic_status = {"state": "pending", "finished_at": None, "error": None}

def _background_diagnostic():
    try:
        report = write_startup_diagnostic()
        _startup_diagnostic_status["state"] = "ready" if not (report or {}).get("error") else "error"
        _startup_diagnostic_status["error"] = (report or {}).get("error")
    except Exception as error:
        _startup_diagnostic_status["state"] = "error"
        _startup_diagnostic_status["error"] = str(error)
    finally:
        _startup_diagnostic_status["finished_at"] = int(time.time())

def write_startup_diagnostic():
    try:
        report = run_full_diagnostic()
        report_path = Path(config["DATA_DIR"]) / "env-check.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        for warning in report.get("warnings", []):
            print(f"[env-check] {warning.get('level', 'info').upper()}: {warning.get('msg', '')}")
        return report
    except Exception as error:
        print(f"[env-check] WARNING: startup diagnostic failed: {error}")
        return {"error": str(error)}
# ===== App =====
app = FastAPI(title="Fliki Clone API", version="0.1.0")



app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
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
    threading.Thread(target=_background_diagnostic, name="env-diagnostic", daemon=True).start()
    yield
    # shutdown: 当前无 cleanup, 留 hook 位置

app.router.lifespan_context = lifespan

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
# ===== Phase D P1-B: alerts webhook =====
_ALERT_AUTH_REQUIRED_MSG = {"error_code": "AUTH_REQUIRED", "message": "missing or invalid token"}

def _require_user_id(request: Request) -> str:
    """rev24 阶段 D P1-B: helper to require authenticated user (admin or user)."""
    from auth_router import get_user_id_from_request as _g
    uid = _g(request)
    if not uid:
        raise HTTPException(status_code=401, detail=_ALERT_AUTH_REQUIRED_MSG)
    return uid


@app.get("/api/alerts/rules")
def list_alert_rules(request: Request):
    """rev24 阶段 D P1-B: list alert rules (auth required)."""
    _require_user_id(request)
    return {"rules": get_rules_info(), "manager_stats": _ALERT_MANAGER.stats()}


@app.post("/api/alerts/eval")
def eval_alerts(request: Request):
    """rev24 阶段 D P1-B: evaluate all rules, fire webhook for triggered ones (auth required)."""
    _require_user_id(request)
    con = get_db()
    try:
        results = eval_rules(con)
        triggered = [r for r in results if r.get("triggered")]
        return {"evaluated": len(results), "triggered": len(triggered), "results": results}
    finally:
        con.close()


@app.post("/api/alerts/reset-throttle")
def reset_alert_throttle(request: Request):
    """rev24 阶段 D P1-B: reset alert throttle (auth required). For testing / manual recovery."""
    _require_user_id(request)
    _ALERT_MANAGER.reset_throttle()
    return {"reset": True, "stats": _ALERT_MANAGER.stats()}



@app.get("/startup-status")
def startup_status():
    return _startup_diagnostic_status

@app.get("/health")
def health():
    """rev24 阶段 D P1-C 收口: liveness + 资源健康 (cpu / disk / queue)."""
    import shutil
    # disk: data 目录所在盘剩余空间
    try:
        du = shutil.disk_usage(str(Path(config["DATA_DIR"])))
        disk_free_gb = round(du.free / 1e9, 2)
        disk_total_gb = round(du.total / 1e9, 2)
    except Exception:
        disk_free_gb = None
        disk_total_gb = None
    # render_queue 当前 backlog (从 workers.render_queue 模块拿, 不是 DB 表)
    queued = active = None
    try:
        from workers.render_queue import get_active_count, get_queue_stats
        active = int(get_active_count())
        stats = get_queue_stats() or {}
        queued = int(stats.get("queued", 0))
    except Exception:
        pass
    return {
        "status": "ok",
        "ts": int(time.time()),
        "cpu_count": os.cpu_count(),
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "render_queue": {"queued": queued, "active": active},
    }
class StyleOut(BaseModel):
    model_config = {"populate_by_name": True}
    id: str = Field(alias="_id")
    name: str
    key: str
    prefix: str | None = None
    suffix: str | None = None
    character_prompt: str | None = None
    composition: str | None = None
    image_prompt_direction: str | None = None
    video_prompt_direction: str | None = None
    thumbnail: str | None = None


def _top_users_by_activity(con, table, n=10):
    """rev24 阶段 D P1-A: top N users by total activity in a table; rest aggregated as 'other' cap.

    Defensive: if table missing user_id column or has no rows, return ([], 0).
    """
    try:
        tcols = {row["name"] for row in con.execute("PRAGMA table_info(" + table + ")").fetchall()}
        if "user_id" not in tcols:
            return ([], 0)
        rows = con.execute(
            "SELECT user_id, COUNT(*) AS cnt FROM " + table + " WHERE user_id IS NOT NULL GROUP BY user_id ORDER BY cnt DESC"
        ).fetchall()
        return ([(str(r[0]), int(r[1])) for r in rows[:n]], sum(int(r[1]) for r in rows[n:]))
    except Exception:
        return ([], 0)


def _emit_user_metrics(con, out):
    """rev24 阶段 D P1-A: emit Prometheus metrics with user/tenant dimension.

    Cardinality cap: top 10 users per table, others aggregated as user_id="other".
    Avoids high-cardinality explosion in TSDB.
    """
    TOP_N = 10

    # 1) render_jobs per user (top N + other)
    out.append("# HELP fliki_render_jobs_per_user_total Render jobs by user_id (top N + other bucket)")
    out.append("# TYPE fliki_render_jobs_per_user_total gauge")
    top_users, _other = _top_users_by_activity(con, "render_jobs", n=TOP_N)
    top_user_ids = {u for u, _ in top_users}
    per_user_status = con.execute(
        "SELECT user_id, status, COUNT(*) FROM render_jobs WHERE user_id IS NOT NULL GROUP BY user_id, status"
    ).fetchall()
    for user_id, status, cnt in per_user_status:
        bucket = user_id if user_id in top_user_ids else "other"
        out.append("fliki_render_jobs_per_user_total{user_id=\"" + str(bucket) + "\", status=\"" + str(status or "unknown") + "\"} " + str(cnt))
    out.append("")

    # 2) workflow_runs per user (top N + other)
    out.append("# HELP fliki_workflow_runs_per_user_total Workflow runs by user_id (top N + other bucket)")
    out.append("# TYPE fliki_workflow_runs_per_user_total gauge")
    top_users_r, _other_r = _top_users_by_activity(con, "workflow_runs", n=TOP_N)
    top_user_ids_r = {u for u, _ in top_users_r}
    per_user_status_r = con.execute(
        "SELECT user_id, status, COUNT(*) FROM workflow_runs WHERE user_id IS NOT NULL GROUP BY user_id, status"
    ).fetchall()
    for user_id, status, cnt in per_user_status_r:
        bucket = user_id if user_id in top_user_ids_r else "other"
        out.append("fliki_workflow_runs_per_user_total{user_id=\"" + str(bucket) + "\", status=\"" + str(status or "unknown") + "\"} " + str(cnt))
    out.append("")

    # 3) top N users by total jobs (rank 1..N)
    out.append("# HELP fliki_top_users_by_jobs Top N users by total render_jobs (rank 1..N)")
    out.append("# TYPE fliki_top_users_by_jobs gauge")
    for rank, (user_id, cnt) in enumerate(top_users, 1):
        out.append("fliki_top_users_by_jobs{user_id=\"" + str(user_id) + "\", rank=\"" + str(rank) + "\"} " + str(cnt))
    out.append("")

    # 4) active users in last 24h (distinct user_id with recent activity)
    out.append("# HELP fliki_active_users_24h Distinct users with activity in last 24h")
    out.append("# TYPE fliki_active_users_24h gauge")
    try:
        active_render = int(con.execute(
            "SELECT COUNT(DISTINCT user_id) FROM render_jobs WHERE user_id IS NOT NULL AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0] or 0)
    except Exception:
        active_render = 0
    try:
        active_run = int(con.execute(
            "SELECT COUNT(DISTINCT user_id) FROM workflow_runs WHERE user_id IS NOT NULL AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0] or 0)
    except Exception:
        active_run = 0
    out.append("fliki_active_users_24h{source=\"render_jobs\"} " + str(active_render))
    out.append("fliki_active_users_24h{source=\"workflow_runs\"} " + str(active_run))
    out.append("")


# ===== Phase 3-5: /metrics (Prometheus format) =====
def _safe_count(con, sql, params=()):
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


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


@app.get("/characters")
def list_characters_route(request: Request = None, gender: str | None = None, limit: int = 50):
    """P3+ 路由: 返回 characters 列表, fliki picker shape [{_id, name, gender, looksCount, thumbnail}].

    - gender (query, 可选): 小写 / 大写都接受, 内部转大写匹配 characters.kind
    - limit 默认 50, 上限 200
    - 公开端点: 无 token 也能查 (跟 voices/gallery 一致)
    """
    return list_characters(gender=gender, limit=limit)


def list_characters(gender: str | None = None, limit: int = 50):
    """characters -> fliki picker shape. kind -> gender (upper); meta_json.looksCount -> looksCount; image_path -> thumbnail."""
    capped_limit = max(1, min(int(limit or 50), 200))
    con = get_db()
    try:
        where = ""
        params: list = []
        if gender:
            where = " WHERE UPPER(kind) = ?"
            params.append(gender.strip().upper())
        params.append(capped_limit)
        rows = con.execute("SELECT * FROM characters" + where + " ORDER BY created_at DESC LIMIT ?", params).fetchall()
        result = []
        for row in rows:
            looks_count = 0
            if row["meta_json"]:
                try:
                    meta = json.loads(row["meta_json"])
                    looks_count = int(meta.get("looksCount") or 0)
                except Exception:
                    looks_count = 0
            result.append({
                "_id": row["id"],
                "name": row["name"],
                "gender": (row["kind"] or "").upper(),
                "looksCount": looks_count,
                "thumbnail": row["image_path"] or "",
            })
        return result
    finally:
        con.close()


@app.get("/render-jobs")
def render_jobs_list(request: Request = None, page: int = 0, limit: int = 50, status: str | None = None):
    """List render_jobs with backward-compatible pagination + user_id isolation.

    ?page=0 or no page  -> return plain list (legacy / frontend callers)
    ?page>=1            -> return {items, total, page, limit, has_more} wrapper

    limit capped 1..100. status optional filter (eq).
    user_id isolation: anon -> empty list, authed -> filter by user_id (D3 fix).
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
            # 兼容旧前端: 直接返 list
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




class RenderCreateBody(BaseModel):
    playback_id: str
    resolution: str = "720p"
    extension: str = "mp4"
    engine: str = "remotion"
    renderer: str = "local"
    props_path: str | None = None

class RenderCancelBody(BaseModel):
    model_config = {"populate_by_name": True}
    job_id: str = Field(alias="jobId")

WORKER_SCRIPT = Path(__file__).parent / "workers" / "remotion_runner.py"
ACTIVE_RENDER_PROCESSES = {}
ACTIVE_RENDER_LOCK = threading.Lock()

WORKER_PROGRESS_PATTERN = re.compile(r"^\[render-progress\]\s+(\d{1,3})$")

def apply_worker_progress(conn, job_id: str, output_line: str):
    match = WORKER_PROGRESS_PATTERN.match(output_line.strip())
    if not match:
        return False
    progress = int(match.group(1))
    if progress < 0 or progress > 100:
        return False
    cursor = conn.execute(
        "UPDATE render_jobs SET status='processing', "
        "progress=CASE WHEN progress < ? THEN ? ELSE progress END WHERE _id=? AND status='processing'",
        (progress, progress, job_id),
    )
    conn.commit()
    return cursor.rowcount > 0
def terminate_process_tree(process):
    if process.poll() is not None:
        return False
    if platform.system() == "Windows":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            text=True,
        )
    else:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    return True
def expire_render_process(process, timed_out):
    timed_out.set()
    return terminate_process_tree(process)
def mark_render_cancelled(conn, job_id: str):
    cursor = conn.execute(
        "UPDATE render_jobs SET status='failed', message=?, finished_at=? "
        "WHERE _id=? AND status IN ('queued', 'processing')",
        (
            "Cancelled by user",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            job_id,
        ),
    )
    conn.commit()
    return cursor.rowcount > 0
def run_render_job(job_id: str, props_path: str, resolution: str, extension: str, engine: str, renderer: str):
    conn = get_db()
    worker_process = None
    timeout_timer = None
    timed_out = threading.Event()
    worker_output = []
    try:
        job = conn.execute(
            "SELECT status FROM render_jobs WHERE _id=?",
            (job_id,),
        ).fetchone()
        if not job or job["status"] != "queued":
            return
        conn.execute(
            "UPDATE render_jobs SET status=?, progress=0 WHERE _id=? AND status='queued'",
            ("processing", job_id),
        )
        conn.commit()

        # rev18 stage C: cloud renderer branch (mock or real provider)
        if renderer == "cloud":
            from workers.cloud_renderer import run_cloud_render_job
            cloud_stop = threading.Event()

            def _cloud_progress(pct):
                try:
                    conn.execute("UPDATE render_jobs SET progress=? WHERE _id=?", (pct, job_id))
                    conn.commit()
                except Exception:
                    pass

            ok2, msg2, output_path_c, started_at_c, finished_at_c = run_cloud_render_job(
                job_id, str(props_path), config["OUTPUT_DIR"], resolution,
                on_progress=_cloud_progress, stop_event=cloud_stop,
            )
            file_rel = None
            try:
                file_rel = str(Path(output_path_c).relative_to(Path(config["OUTPUT_DIR"])))
            except Exception:
                file_rel = output_path_c
            conn.execute(
                "UPDATE render_jobs SET status=?, progress=?, file=?, message=?, finished_at=? WHERE _id=?",
                ("success" if ok2 else "failed", 100 if ok2 else 0, file_rel if ok2 else None, msg2, finished_at_c, job_id),
            )
            conn.commit()
            return



        popen_options = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if platform.system() == "Windows":
            popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_options["start_new_session"] = True

        worker_process = subprocess.Popen(
            ["python", str(WORKER_SCRIPT), "--job-id", job_id,
             "--props", str(props_path), "--resolution", resolution,
             "--extension", extension, "--output-dir", config["OUTPUT_DIR"]],
            **popen_options,
        )
        with ACTIVE_RENDER_LOCK:
            ACTIVE_RENDER_PROCESSES[job_id] = worker_process

        current = conn.execute(
            "SELECT status FROM render_jobs WHERE _id=?",
            (job_id,),
        ).fetchone()
        if not current or current["status"] != "processing":
            terminate_process_tree(worker_process)
            return

        timeout_timer = threading.Timer(
            config["RENDER_TIMEOUT_SECONDS"],
            expire_render_process,
            args=(worker_process, timed_out),
        )
        timeout_timer.daemon = True
        timeout_timer.start()

        if worker_process.stdout is None:
            raise RuntimeError("Render worker stdout pipe was not created")
        for output_line in worker_process.stdout:
            worker_output.append(output_line)
            worker_output = worker_output[-200:]
            apply_worker_progress(conn, job_id, output_line)
        return_code = worker_process.wait()

        current = conn.execute(
            "SELECT status, message FROM render_jobs WHERE _id=?",
            (job_id,),
        ).fetchone()
        if current and current["status"] == "failed" and current["message"] == "Cancelled by user":
            return

        finished_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        if timed_out.is_set():
            conn.execute(
                "UPDATE render_jobs SET status='failed', message=?, finished_at=? WHERE _id=?",
                (
                    f"Render timed out after {config['RENDER_TIMEOUT_SECONDS']} seconds",
                    finished_at,
                    job_id,
                ),
            )
        elif return_code == 0:
            out_dir = Path(config["OUTPUT_DIR"]) / job_id
            out_dir.mkdir(parents=True, exist_ok=True)
            conn.execute(
                "UPDATE render_jobs SET status=?, progress=100, message=NULL, "
                "file=?, thumbnail=?, thumbnail_preview=?, media_generated_id=?, finished_at=? WHERE _id=?",
                (
                    "success",
                    f"{job_id}/{job_id}.{extension}",
                    f"{job_id}/{job_id}_thumb.jpg",
                    f"{job_id}/{job_id}_thumbPreview.jpg",
                    job_id,
                    finished_at,
                    job_id,
                ),
            )
        else:
            conn.execute(
                "UPDATE render_jobs SET status='failed', message=?, finished_at=? WHERE _id=?",
                ("".join(worker_output)[-2000:], finished_at, job_id),
            )
        conn.commit()
    except Exception as error:
        conn.execute(
            "UPDATE render_jobs SET status='failed', message=?, finished_at=? "
            "WHERE _id=? AND status IN ('queued', 'processing')",
            (
                str(error)[:2000],
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                job_id,
            ),
        )
        conn.commit()
    finally:
        if timeout_timer:
            timeout_timer.cancel()
        if worker_process:
            with ACTIVE_RENDER_LOCK:
                if ACTIVE_RENDER_PROCESSES.get(job_id) is worker_process:
                    ACTIVE_RENDER_PROCESSES.pop(job_id, None)
        conn.close()
# rev24 阶段 C P2-A: 详情端点 + user_id 校验
@app.get("/render-jobs/{job_id}", response_model=dict)
def render_job_detail(job_id: str, request: Request = None):
    """按 job_id 查详情, 跨用户 404 (防枚举)."""
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
        # 跨用户: 隐藏
        if job["user_id"] is not None and user_id != job["user_id"]:
            raise HTTPException(status_code=404, detail="Render job not found")
        return dict(job)
    finally:
        conn.close()


@app.post("/render.create")
def render_create(body: RenderCreateBody, background_tasks: BackgroundTasks, request: Request = None):
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


# rev24 阶段 C P2-A: 带 user_id 鉴权的渲染视频流, 替代 /outputs 静态路径 (后者无鉴权)
@app.get("/render/{filename}")
def render_video(filename: str, request: Request = None):
    """按 filename 找 render_jobs, user_id 匹配才返回文件. 跨用户/匿名一律 404 防枚举.
    
    注意: /outputs/{file} StaticFiles mount 仍存在 (兼容其他用途, 如 avatar/voice preview),
    但渲染视频统一走 /render/{filename} 以享受鉴权.
    """
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
        # 没记录 OR 跨用户: 一律 404 防枚举
        if not job or job["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Render file not found")
        file_path = OUTPUT_DIR / filename
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="Render file not found")
        return FileResponse(str(file_path))
    finally:
        conn.close()


@app.post("/render.cancel")
def render_cancel(body: RenderCancelBody, request: Request = None):
    # rev24 阶段 C P2-A: user_id 校验, 跨用户 404 (防越权取消)
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
    # 跨用户: 隐藏 (返回 404 而非 403, 防枚举)
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
    terminated = terminate_process_tree(worker_process) if worker_process else False
    return {
        "jobId": body.job_id,
        "status": "cancelled",
        "cancelled": True,
        "terminated": terminated,
    }
# ===== Provider config (decision 5: LLM 手动配置) =====
@app.get("/providers")
def list_providers():
    return DEFAULT_PROVIDERS

@app.get("/")
def root():
    return {"api": "fliki-clone", "version": app.version, "endpoints": [
        "/health", "/styles", "/media-samples",
        "/render.latest", "/render.create", "/providers"
    ]}

def _emit_tenant_metrics(con, out):
    """rev24 阶段 D D1-1: tenant 维度 (user_id md5 哈希分 4 桶, 确定性).

    users 表无 tenant_id 字段, 暂用 hash(user_id)[0] -> tenant_a/b/c/d 模拟多租户聚合,
    后续真做多租户时切到 users.tenant_id 直接读.
    """
    def _bucket(user_id):
        h = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()
        n = int(h[0], 16) % 4
        return "tenant_" + ("a", "b", "c", "d")[n]

    # 1) render_jobs per tenant
    out.append("# HELP fliki_render_jobs_per_tenant_total Render jobs by tenant bucket (md5(user_id) % 4)")
    out.append("# TYPE fliki_render_jobs_per_tenant_total gauge")
    try:
        rows = con.execute(
            "SELECT user_id, status, COUNT(*) FROM render_jobs WHERE user_id IS NOT NULL GROUP BY user_id, status"
        ).fetchall()
        agg = {}
        for user_id, status, cnt in rows:
            b = _bucket(user_id)
            agg[(b, status or "unknown")] = agg.get((b, status or "unknown"), 0) + cnt
        for (b, status), cnt in sorted(agg.items()):
            out.append("fliki_render_jobs_per_tenant_total{tenant=\"" + b + "\", status=\"" + str(status) + "\"} " + str(cnt))
    except Exception as e:
        out.append("# render_jobs per tenant error: " + str(e))
    out.append("")

    # 2) workflow_runs per tenant
    out.append("# HELP fliki_workflow_runs_per_tenant_total Workflow runs by tenant bucket")
    out.append("# TYPE fliki_workflow_runs_per_tenant_total gauge")
    try:
        rows = con.execute(
            "SELECT user_id, status, COUNT(*) FROM workflow_runs WHERE user_id IS NOT NULL GROUP BY user_id, status"
        ).fetchall()
        agg = {}
        for user_id, status, cnt in rows:
            b = _bucket(user_id)
            agg[(b, status or "unknown")] = agg.get((b, status or "unknown"), 0) + cnt
        for (b, status), cnt in sorted(agg.items()):
            out.append("fliki_workflow_runs_per_tenant_total{tenant=\"" + b + "\", status=\"" + str(status) + "\"} " + str(cnt))
    except Exception as e:
        out.append("# workflow_runs per tenant error: " + str(e))
    out.append("")

    # 3) active users per tenant in last 24h
    out.append("# HELP fliki_active_users_24h_per_tenant Active users in last 24h by tenant bucket")
    out.append("# TYPE fliki_active_users_24h_per_tenant gauge")
    try:
        for src in ("render_jobs", "workflow_runs"):
            rows = con.execute(
                "SELECT DISTINCT user_id FROM " + src + " WHERE user_id IS NOT NULL AND created_at >= datetime('now', '-1 day')"
            ).fetchall()
            bucket_users = {"tenant_a": set(), "tenant_b": set(), "tenant_c": set(), "tenant_d": set()}
            for (u,) in rows:
                bucket_users[_bucket(u)].add(u)
            for b, users in sorted(bucket_users.items()):
                if users:
                    out.append("fliki_active_users_24h_per_tenant{tenant=\"" + b + "\", source=\"" + src + "\"} " + str(len(users)))
    except Exception as e:
        out.append("# active users per tenant error: " + str(e))
    out.append("")

