import json, os, sys, uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS autoedit_uploads (
  id TEXT PRIMARY KEY, filename TEXT NOT NULL, stored_path TEXT NOT NULL,
  size_bytes INTEGER NOT NULL, duration_seconds REAL, width INTEGER, height INTEGER,
  container TEXT, status TEXT NOT NULL DEFAULT 'queued', message TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autoedit_status ON autoedit_uploads(status, created_at DESC);

CREATE TABLE IF NOT EXISTS autoedit_drafts (
  id TEXT PRIMARY KEY, upload_id TEXT NOT NULL, title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft', version INTEGER NOT NULL DEFAULT 1,
  language TEXT NOT NULL DEFAULT 'zh-CN', confirmed_snapshot_json TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, confirmed_at TEXT,
  FOREIGN KEY(upload_id) REFERENCES autoedit_uploads(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_autoedit_drafts_status ON autoedit_drafts(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS autoedit_segments (
  id TEXT PRIMARY KEY, autoedit_draft_id TEXT NOT NULL, position INTEGER NOT NULL,
  start_seconds REAL NOT NULL, end_seconds REAL NOT NULL, text TEXT NOT NULL, subtitle TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'keep', asset_kind TEXT, asset_query TEXT, broll_url TEXT,
  music_volume REAL, notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(autoedit_draft_id) REFERENCES autoedit_drafts(id) ON DELETE CASCADE,
  UNIQUE(autoedit_draft_id, position)
);
CREATE INDEX IF NOT EXISTS idx_autoedit_segments_draft ON autoedit_segments(autoedit_draft_id, position);

CREATE TABLE IF NOT EXISTS autoedit_runs (
  id TEXT PRIMARY KEY, autoedit_draft_id TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued', progress INTEGER NOT NULL DEFAULT 0,
  render_job_id TEXT, message TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished_at TEXT,
  FOREIGN KEY(autoedit_draft_id) REFERENCES autoedit_drafts(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_autoedit_runs_draft ON autoedit_runs(autoedit_draft_id, created_at DESC);

CREATE TABLE IF NOT EXISTS autoedit_nodes (
  id TEXT PRIMARY KEY, autoedit_run_id TEXT NOT NULL, segment_id TEXT, node_type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued', progress INTEGER NOT NULL DEFAULT 0, provider TEXT,
  attempt INTEGER NOT NULL DEFAULT 1, input_json TEXT, result_json TEXT, message TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished_at TEXT,
  FOREIGN KEY(autoedit_run_id) REFERENCES autoedit_runs(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_autoedit_nodes_run ON autoedit_nodes(autoedit_run_id, node_type, status);
"""


def now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def run_ffprobe(path):
    import json, subprocess, shutil
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe not found in PATH")
    cmd = [shutil.which("ffprobe"), "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    # Windows GBK 问题: 不传 text=True, 用 bytes + 手动 utf-8 decode + replace
    proc = subprocess.run(cmd, capture_output=True, timeout=30)
    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()[:300]
        raise RuntimeError(f"ffprobe failed (rc={proc.returncode}): {err}")
    raw = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if not raw:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()[:300]
        raise RuntimeError(f"ffprobe returned empty stdout. stderr: {err}")
    data = json.loads(raw)
    fmt = data.get("format", {})
    duration = float(fmt.get("duration", 0)) if fmt.get("duration") else 0.0
    container = (fmt.get("format_name") or "").split(",")[0] or "unknown"
    width = height = 0
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            break
    return {"duration_seconds": round(duration, 3), "width": width, "height": height, "container": container}


def detect_silences(path, noise_db="-30dB", min_duration=0.4):
    import subprocess, shutil
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg_bin, "-hide_banner", "-nostats", "-i", str(path), "-af", f"silencedetect=noise={noise_db}:d={min_duration}", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=180)
    stderr_text = (proc.stderr or b"").decode("utf-8", errors="replace")
    silences = []
    last_start = None
    for line in stderr_text.splitlines():
        line = line.strip()
        if "silence_start:" in line:
            try:
                last_start = float(line.split("silence_start:")[1].strip())
            except ValueError:
                last_start = None
        elif "silence_end:" in line and last_start is not None:
            try:
                end = float(line.split("silence_end:")[1].split()[0].strip())
                silences.append((round(last_start, 3), round(end, 3)))
            except ValueError:
                pass
            last_start = None
    return silences


def transcribe_audio(path, language="zh"):
    base = os.getenv("OPENAI_BASE_URL") or os.getenv("WHISPER_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("WHISPER_API_KEY")
    if base and api_key:
        return _transcribe_via_api(path, language, base, api_key)
    return _transcribe_local(path, language)


def _transcribe_local(path, language):
    from faster_whisper import WhisperModel
    model_name = os.getenv("FLIKI_WHISPER_MODEL", "base")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(path), language=language, vad_filter=True)
    return [
        {"start": round(seg.start, 3), "end": round(seg.end, 3), "text": (seg.text or "").strip()}
        for seg in segments if (seg.text or "").strip()
    ]


def _transcribe_via_api(path, language, base, api_key):
    from openai import OpenAI
    client = OpenAI(base_url=base, api_key=api_key)
    with open(path, "rb") as handle:
        response = client.audio.transcriptions.create(
            model=os.getenv("FLIKI_WHISPER_MODEL", "whisper-1"),
            file=handle,
            language=language,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )
    out = []
    for seg in getattr(response, "segments", []) or []:
        text = (getattr(seg, "text", "") or "").strip()
        if not text:
            continue
        out.append({
            "start": round(float(getattr(seg, "start", 0)), 3),
            "end": round(float(getattr(seg, "end", 0)), 3),
            "text": text,
        })
    if not out and getattr(response, "text", None):
        out.append({"start": 0.0, "end": 0.0, "text": response.text.strip()})
    return out


def plan_cuts(silences, total_duration, target_segments=6, max_segment=12.0, min_segment=2.5):
    long_silences = [s for s in silences if (s[1] - s[0]) >= 0.6]
    cut_points = sorted({round(s[0], 3) for s in long_silences} | {0.0, round(total_duration, 3)})
    if len(cut_points) - 1 <= target_segments:
        boundaries = cut_points
    else:
        step = max(1, (len(cut_points) - 1) // target_segments)
        boundaries = [cut_points[i] for i in range(0, len(cut_points), step)]
        if boundaries[-1] != cut_points[-1]:
            boundaries.append(cut_points[-1])
    segments = []
    for index in range(len(boundaries) - 1):
        start = boundaries[index]
        end = boundaries[index + 1]
        if end - start > max_segment:
            pieces = int((end - start) // max_segment) + 1
            piece = (end - start) / pieces
            for piece_index in range(pieces):
                seg_start = round(start + piece * piece_index, 3)
                seg_end = round(start + piece * (piece_index + 1), 3)
                if seg_end - seg_start >= min_segment:
                    segments.append((seg_start, seg_end))
        elif end - start >= min_segment:
            segments.append((start, end))
    return segments


def attach_transcript(cut_segments, transcript):
    enriched = []
    for start, end in cut_segments:
        pieces = []
        for seg in transcript or []:
            overlap = max(0.0, min(end, seg["end"]) - max(start, seg["start"]))
            seg_len = max(0.001, seg["end"] - seg["start"])
            if overlap / seg_len >= 0.4:
                pieces.append(seg["text"].strip())
        enriched.append({"start_seconds": start, "end_seconds": end, "text": " ".join(pieces).strip()})
    return enriched


def build_draft_segments(cut_segments):
    out = []
    for index, seg in enumerate(cut_segments):
        text = seg["text"] or f"片段 {index + 1}"
        kind = "keep"
        notes = ""
        if len(text) < 6:
            kind = "trim"
            notes = "短句，建议精简或保留为静音过渡。"
        elif any(marker in text for marker in ("嗯", "呃", "啊", "um", "uh", "like", "you know")):
            kind = "trim"
            notes = "含语气词，已标记为精简。"
        out.append({
            "id": uuid.uuid4().hex,
            "position": index,
            "start_seconds": round(seg["start_seconds"], 3),
            "end_seconds": round(seg["end_seconds"], 3),
            "text": text,
            "subtitle": text,
            "kind": kind,
            "asset_kind": "stock" if text else None,
            "asset_query": text[:80] or None,
            "broll_url": None,
            "music_volume": 0.12,
            "notes": notes,
        })
    return out


def draft_payload(connection, draft_id):
    draft = connection.execute("SELECT * FROM autoedit_drafts WHERE id=?", (draft_id,)).fetchone()
    if draft is None:
        raise HTTPException(status_code=404, detail="Auto-edit draft not found")
    segments = connection.execute("SELECT * FROM autoedit_segments WHERE autoedit_draft_id=? ORDER BY position", (draft_id,)).fetchall()
    upload = connection.execute("SELECT * FROM autoedit_uploads WHERE id=?", (draft["upload_id"],)).fetchone()
    return {
        "id": draft["id"],
        "upload_id": draft["upload_id"],
        "title": draft["title"],
        "status": draft["status"],
        "version": draft["version"],
        "language": draft["language"],
        "duration_seconds": round(sum(seg["end_seconds"] - seg["start_seconds"] for seg in segments), 3),
        "media": {
            "stored_path": upload["stored_path"],
            "duration_seconds": upload["duration_seconds"],
            "width": upload["width"],
            "height": upload["height"],
            "container": upload["container"],
        },
        "segments": [dict(seg) for seg in segments],
        "created_at": draft["created_at"],
        "updated_at": draft["updated_at"],
        "confirmed_at": draft["confirmed_at"],
    }


def require_editable(connection, draft_id):
    row = connection.execute("SELECT status FROM autoedit_drafts WHERE id=?", (draft_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Auto-edit draft not found")
    if row["status"] != "draft":
        raise HTTPException(status_code=409, detail="Confirmed auto-edit drafts are immutable")


def record_revision(connection, draft_id):
    payload = draft_payload(connection, draft_id)
    version = payload["version"] + 1
    import json
    snapshot = json.dumps(payload, ensure_ascii=False, default=str)
    connection.execute(
        "INSERT INTO autoedit_revisions (id, autoedit_draft_id, version, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, draft_id, version, snapshot, now_iso()),
    )
    connection.execute("UPDATE autoedit_drafts SET version=?, updated_at=? WHERE id=?", (version, now_iso(), draft_id))


def ensure_revisions_table(connection):
    connection.execute(
        "CREATE TABLE IF NOT EXISTS autoedit_revisions ("
        "id TEXT PRIMARY KEY, autoedit_draft_id TEXT NOT NULL, version INTEGER NOT NULL, "
        "snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL, "
        "FOREIGN KEY(autoedit_draft_id) REFERENCES autoedit_drafts(id) ON DELETE CASCADE, "
        "UNIQUE(autoedit_draft_id, version))"
    )
    connection.commit()


class SegmentPatchBody(BaseModel):
    kind: str | None = Field(default=None, pattern="^(keep|trim|drop)$")
    subtitle: str | None = Field(default=None, min_length=1, max_length=2000)
    asset_kind: str | None = Field(default=None, pattern="^(stock|none)$")
    asset_query: str | None = Field(default=None, max_length=200)
    start_seconds: float | None = Field(default=None, ge=0)
    end_seconds: float | None = Field(default=None, gt=0)
    music_volume: float | None = Field(default=None, ge=0, le=1)

    @classmethod
    def require_change(cls, value):
        if not value.model_fields_set:
            raise ValueError("At least one field is required")
        return value


class ReorderBody(BaseModel):
    segment_ids: list[str] = Field(min_length=1, max_length=200)


class ConfirmBody(BaseModel):
    language: str | None = Field(default=None, min_length=2, max_length=32)


def create_router(get_db, render_create, render_body_class, max_upload_bytes):
    router = APIRouter(prefix="/autoedit", tags=["autoedit"])

    @router.post("/uploads")
    async def upload_video(file: UploadFile = File(...)):
        if not file.content_type or not file.content_type.startswith("video/"):
            raise HTTPException(status_code=415, detail="Only video uploads are accepted")
        upload_dir = ROOT / "data" / "autoedit_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        upload_id = uuid.uuid4().hex
        stored_path = upload_dir / f"{upload_id}-{file.filename or 'video.mp4'}"
        written = 0
        with stored_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_upload_bytes:
                    out.close()
                    stored_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail=f"Upload exceeds {max_upload_bytes} bytes")
                out.write(chunk)
        with get_db() as connection:
            connection.executescript(SCHEMA_SQL)
            ensure_revisions_table(connection)
            meta = run_ffprobe(str(stored_path))
            connection.execute(
                "INSERT INTO autoedit_uploads (id, filename, stored_path, size_bytes, duration_seconds, width, height, container, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (upload_id, file.filename or "video.mp4", str(stored_path), written, meta["duration_seconds"], meta["width"], meta["height"], meta["container"], "uploaded", now_iso()),
            )
            connection.commit()
            return {"id": upload_id, "filename": file.filename, "size_bytes": written, **meta}
    @router.post("/uploads/{upload_id}/drafts")
    def create_draft(upload_id: str, language: str = "zh-CN"):
        with get_db() as connection:
            connection.executescript(SCHEMA_SQL)
            ensure_revisions_table(connection)
            upload = connection.execute("SELECT * FROM autoedit_uploads WHERE id=?", (upload_id,)).fetchone()
            if upload is None:
                raise HTTPException(status_code=404, detail="Upload not found")
            if not upload["duration_seconds"]:
                raise HTTPException(status_code=409, detail="Upload has no duration yet")
            silences = detect_silences(upload["stored_path"])
            cuts = plan_cuts(silences, upload["duration_seconds"])
            transcript = transcribe_audio(upload["stored_path"], language=language.split("-")[0])
            enriched = attach_transcript(cuts, transcript)
            draft_segments = build_draft_segments(enriched)
            draft_id = uuid.uuid4().hex
            timestamp = now_iso()
            connection.execute(
                "INSERT INTO autoedit_drafts (id, upload_id, title, status, version, language, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?, ?)",
                (draft_id, upload_id, f"剪辑 {upload['filename']}", "draft", language, timestamp, timestamp),
            )
            for seg in draft_segments:
                connection.execute(
                    "INSERT INTO autoedit_segments (id, autoedit_draft_id, position, start_seconds, end_seconds, text, subtitle, kind, asset_kind, asset_query, broll_url, music_volume, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (seg["id"], draft_id, seg["position"], seg["start_seconds"], seg["end_seconds"], seg["text"], seg["subtitle"], seg["kind"], seg["asset_kind"], seg["asset_query"], seg["broll_url"], seg["music_volume"], seg["notes"], timestamp, timestamp),
                )
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.get("/drafts/{draft_id}")
    def get_draft(draft_id: str):
        with get_db() as connection:
            ensure_revisions_table(connection)
            return draft_payload(connection, draft_id)
    @router.patch("/drafts/{draft_id}/segments/{segment_id}")
    def update_segment(draft_id: str, segment_id: str, body: SegmentPatchBody):
        with get_db() as connection:
            ensure_revisions_table(connection)
            require_editable(connection, draft_id)
            if connection.execute("SELECT id FROM autoedit_segments WHERE id=? AND autoedit_draft_id=?", (segment_id, draft_id)).fetchone() is None:
                raise HTTPException(status_code=404, detail="Segment not found")
            SegmentPatchBody.require_change(body)
            values = body.model_dump(exclude_unset=True)
            if "start_seconds" in values and "end_seconds" in values and values["end_seconds"] <= values["start_seconds"]:
                raise HTTPException(status_code=422, detail="end_seconds must be greater than start_seconds")
            assignments = ", ".join(f"{name}=?" for name in values)
            connection.execute(
                f"UPDATE autoedit_segments SET {assignments}, updated_at=? WHERE id=?",
                (*values.values(), now_iso(), segment_id),
            )
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.post("/drafts/{draft_id}/reorder")
    def reorder_segments(draft_id: str, body: ReorderBody):
        with get_db() as connection:
            ensure_revisions_table(connection)
            require_editable(connection, draft_id)
            current = [row["id"] for row in connection.execute("SELECT id FROM autoedit_segments WHERE autoedit_draft_id=? ORDER BY position", (draft_id,)).fetchall()]
            if len(body.segment_ids) != len(set(body.segment_ids)) or set(body.segment_ids) != set(current):
                raise HTTPException(status_code=422, detail="segment_ids must contain every segment exactly once")
            for tmp_position, seg_id in enumerate(body.segment_ids):
                connection.execute("UPDATE autoedit_segments SET position=? WHERE id=?", (-tmp_position - 1, seg_id))
            for position, seg_id in enumerate(body.segment_ids):
                connection.execute("UPDATE autoedit_segments SET position=?, updated_at=? WHERE id=?", (position, now_iso(), seg_id))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.delete("/drafts/{draft_id}/segments/{segment_id}")
    def delete_segment(draft_id: str, segment_id: str):
        with get_db() as connection:
            ensure_revisions_table(connection)
            require_editable(connection, draft_id)
            if connection.execute("SELECT COUNT(*) FROM autoedit_segments WHERE autoedit_draft_id=?", (draft_id,)).fetchone()[0] <= 1:
                raise HTTPException(status_code=409, detail="A draft must contain at least one segment")
            row = connection.execute("SELECT position FROM autoedit_segments WHERE id=? AND autoedit_draft_id=?", (segment_id, draft_id)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="Segment not found")
            connection.execute("UPDATE autoedit_segments SET kind='drop' WHERE id=?", (segment_id,))
            record_revision(connection, draft_id)
            connection.commit()
            return draft_payload(connection, draft_id)
    @router.post("/drafts/{draft_id}/confirm")
    def confirm_draft(draft_id: str, body: ConfirmBody | None = None):
        with get_db() as connection:
            ensure_revisions_table(connection)
            payload = draft_payload(connection, draft_id)
            if payload["status"] == "confirmed":
                return payload
            kept = [seg for seg in payload["segments"] if seg["kind"] != "drop"]
            if not kept:
                raise HTTPException(status_code=409, detail="No segments kept after edits")
            import json
            confirmed_at = now_iso()
            connection.execute(
                "UPDATE autoedit_drafts SET status='confirmed', confirmed_snapshot_json=?, confirmed_at=?, updated_at=? WHERE id=? AND status='draft'",
                (json.dumps(payload, ensure_ascii=False, default=str), confirmed_at, confirmed_at, draft_id),
            )
            connection.commit()
            return draft_payload(connection, draft_id)
    return router
