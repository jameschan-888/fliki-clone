"""Fliki 还原后端 - FastAPI 主入口"""
import json, os, platform, re, signal, sqlite3, threading, time, uuid, subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config import config, DEFAULT_PROVIDERS
from workflow_drafts import create_router as create_workflow_drafts_router
from provider_config import create_router as create_provider_config_router, seed_runtime_providers
from workflow_pipeline import create_router as create_workflow_pipeline_router
from autoedit import create_router as create_autoedit_router
from autoedit_pipeline import create_router as create_autoedit_pipeline_router
from env_check_router import create_router as create_env_check_router
from env_check import run_full_diagnostic
from voice_gallery import create_router as create_voice_gallery_router, ensure_voices
from voice_clone_router import create_router as create_voice_clone_router
from avatar_clone_router import create_router as create_avatar_clone_router

# ===== DB =====
def get_db():
    conn = sqlite3.connect(config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    schema = Path(__file__).parent / "db" / "schema.sql"
    conn = get_db()
    try:
        conn.executescript(schema.read_text(encoding="utf-8"))
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(scene_drafts)").fetchall()}
        migrated = False
        if columns and "voice" not in columns:
            conn.execute("ALTER TABLE scene_drafts ADD COLUMN voice TEXT NOT NULL DEFAULT 'zh-CN-XiaoxiaoNeural'")
            migrated = True
        if columns and "avatar" not in columns:
            conn.execute("ALTER TABLE scene_drafts ADD COLUMN avatar TEXT")
            migrated = True
        if columns and "avatar_layout" not in columns:
            conn.execute("ALTER TABLE scene_drafts ADD COLUMN avatar_layout TEXT")
            migrated = True
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

@app.on_event("startup")
def startup():
    if init_db():
        print("[database] Added scene_drafts.voice compatibility column")
    connection = get_db()
    try:
        seed_runtime_providers(connection)
        ensure_voices(connection)
    finally:
        connection.close()
    # write_startup_diagnostic 联网探测耗 4-36s；改后台线程避免阻塞 startup
    threading.Thread(target=_background_diagnostic, name="env-diagnostic", daemon=True).start()

app.include_router(create_workflow_drafts_router(get_db))
app.include_router(create_provider_config_router(get_db))
VOICE_PREVIEW_DIR = Path(config["DATA_DIR"]) / "voice_previews"
VOICE_PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/voice-previews", StaticFiles(directory=str(VOICE_PREVIEW_DIR)), name="voice-previews")
OUTPUT_DIR = Path(config["OUTPUT_DIR"])
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.include_router(create_voice_gallery_router(get_db, VOICE_PREVIEW_DIR))
app.include_router(create_voice_clone_router(get_db, VOICE_PREVIEW_DIR))
app.include_router(create_avatar_clone_router(get_db))

@app.get("/startup-status")
def startup_status():
    return _startup_diagnostic_status

@app.get("/health")
def health():
    return {"status": "ok", "ts": int(time.time())}

# ===== Phase 2: styles + media_samples =====
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

@app.get("/styles", response_model=list[StyleOut])
def list_styles(enabled_only: bool = True):
    conn = get_db()
    q = "SELECT * FROM styles WHERE is_enabled=1" if enabled_only else "SELECT * FROM styles"
    rows = conn.execute(q).fetchall()
    conn.close()
    return [dict(r) for r in rows]

class SampleOut(BaseModel):
    model_config = {"populate_by_name": True}
    id: str = Field(alias="_id")
    type: str
    file_path: str | None = None
    name: str | None = None
    duration: float | None = None
    aspect_ratio: str | None = None
    quality: str | None = None
    model: str | None = None
    style: str | None = None
    prompt: str | None = None

@app.get("/media-samples", response_model=list[SampleOut])
def list_samples(type: str | None = None, model: str | None = None, limit: int = 50):
    conn = get_db()
    clauses = []
    params = []
    if type:
        clauses.append("type=?")
        params.append(type)
    if model:
        clauses.append("model=?")
        params.append(model)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM media_samples{where} LIMIT ?", params + [limit]).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ===== Phase 2: characters =====
class CharacterOut(BaseModel):
    model_config = {"populate_by_name": True}
    id: str = Field(alias="_id")
    name: str
    gender: str
    looks_count: int = Field(alias="looksCount")
    thumbnail: str | None = None

@app.get("/characters", response_model=list[CharacterOut])
def list_characters(gender: str | None = None, limit: int = 100):
    conn = get_db()
    clauses = []
    params = []
    if gender:
        clauses.append("kind=?")
        params.append(gender.lower())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    safe_limit = max(1, min(limit, 200))
    rows = conn.execute(
        f"SELECT * FROM characters{where} ORDER BY name LIMIT ?",
        params + [safe_limit],
    ).fetchall()
    conn.close()

    characters = []
    for row in rows:
        item = dict(row)
        try:
            metadata = json.loads(item.get("meta_json") or "{}")
        except json.JSONDecodeError:
            metadata = {}
        characters.append({
            "_id": item["id"],
            "name": item["name"],
            "gender": item["kind"].upper(),
            "looksCount": int(metadata.get("looksCount", 0)),
            "thumbnail": item.get("image_path"),
        })
    return characters
# ===== Phase 3: render.latest + render.create =====
class RenderJobOut(BaseModel):
    id: str
    playback_id: str
    status: str
    progress: int
    resolution: str | None = None
    extension: str | None = None
    renderer: str | None = None
    engine: str | None = None
    message: str | None = None
    media_generated_id: dict | None = None
    file: str | None = None
    thumbnail: str | None = None
    thumbnail_preview: str | None = None
    created_at: str | None = None

@app.get("/render.latest", response_model=dict)
def render_latest(playback_id: str):
    conn = get_db()
    job = conn.execute(
        "SELECT * FROM render_jobs WHERE playback_id=? ORDER BY created_at DESC LIMIT 1",
        (playback_id,)
    ).fetchone()
    conn.close()
    if not job:
        return {"renderRecent": None, "renderSuccess": None}
    j = dict(job)
    mg_id = j.get("media_generated_id")
    media_gen = None
    if mg_id:
        media_gen = {
            "_id": mg_id, "type": "video",
            "file": j.get("file"),
            "filesAssociated": [],
            "thumbnail": j.get("thumbnail"),
            "thumbnailPreview": j.get("thumbnail_preview"),
        }
    job_out = {
        "_id": j["_id"], "status": j["status"], "progress": j["progress"],
        "resolution": j.get("resolution"), "extension": j.get("extension"),
        "renderer": j.get("renderer"), "engine": j.get("engine"), "message": j.get("message"),
        "createdAt": j.get("created_at"), "mediaGeneratedId": media_gen,
    }
    if j["status"] == "success":
        return {"renderRecent": job_out, "renderSuccess": job_out}
    return {"renderRecent": job_out, "renderSuccess": None}

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
@app.post("/render.create")
def render_create(body: RenderCreateBody, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex[:24]
    conn = get_db()
    conn.execute(
        "INSERT INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, created_at) " +
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (job_id, body.playback_id, "queued", 0,
         body.resolution, body.extension, body.renderer, body.engine,
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

@app.post("/render.cancel")
def render_cancel(body: RenderCancelBody):
    conn = get_db()
    job = conn.execute(
        "SELECT status FROM render_jobs WHERE _id=?",
        (body.job_id,),
    ).fetchone()
    if not job:
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
