"""Auto-edit pipeline: 确认后执行 ffmpeg 裁剪+拼接, 输出真实 mp4"""
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException


def _now():
    return datetime.now(timezone.utc).isoformat()


def _run_id(prefix="autoedit"):
    return f"{prefix}-{uuid.uuid4().hex[:20]}"


# ============ helpers ============

def _ffprobe_duration(path):
    """读 ffprobe duration 秒"""
    import shutil
    bin_path = shutil.which("ffprobe") or "ffprobe"
    cmd = [bin_path, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    proc = subprocess.run(cmd, capture_output=True, timeout=20)
    raw = (proc.stdout or b"").decode("utf-8", errors="replace").strip()
    if proc.returncode != 0 or not raw:
        return None
    return round(float(raw), 3)


def _write_srt(segments, path):
    """写 srt 字幕, 单条"""
    with open(path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments, 1):
            s = seg["start"]
            e = seg["end"]
            f.write(f"{idx}\n")
            f.write(f"{_srt_ts(s)} --> {_srt_ts(e)}\n")
            f.write(f"{seg['text']}\n\n")


def _srt_ts(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{int(s):02d},{int((s - int(s)) * 1000):03d}"


def _escape_drawtext(text):
    """转义 drawtext 文本"""
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)


def _node_payload(row):
    return {
        "id": row["id"],
        "segment_id": row["segment_id"],
        "node_type": row["node_type"],
        "status": row["status"],
        "progress": row["progress"],
        "provider": row["provider"],
        "attempt": row["attempt"],
        "result": json.loads(row["result_json"] or "null"),
        "message": row["message"],
    }


def _run_payload(conn, run_id):
    row = conn.execute("SELECT * FROM autoedit_runs WHERE id=?", (run_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Auto-edit run not found")
    nodes = conn.execute(
        "SELECT * FROM autoedit_nodes WHERE autoedit_run_id=? ORDER BY created_at, id",
        (run_id,),
    ).fetchall()
    return {
        "id": row["id"],
        "autoedit_draft_id": row["autoedit_draft_id"],
        "status": row["status"],
        "progress": row["progress"],
        "output_path": row["output_path"] or row["render_job_id"],
        "message": row["message"],
        "nodes": [_node_payload(n) for n in nodes],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "finished_at": row["finished_at"],
    }


def _ensure_node(conn, run_id, segment_id, node_type, input_data):
    """节点幂等: 已成功不再重跑"""
    row = conn.execute(
        "SELECT * FROM autoedit_nodes WHERE autoedit_run_id=? AND (segment_id IS ? OR segment_id=?) AND node_type=?",
        (run_id, segment_id, segment_id, node_type),
    ).fetchone()
    if row:
        return row
    node_id = uuid.uuid4().hex
    ts = _now()
    conn.execute(
        "INSERT INTO autoedit_nodes (id, autoedit_run_id, segment_id, node_type, status, progress, input_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'queued', 0, ?, ?, ?)",
        (node_id, run_id, segment_id, node_type, json.dumps(input_data, ensure_ascii=False), ts, ts),
    )
    conn.commit()
    return conn.execute("SELECT * FROM autoedit_nodes WHERE id=?", (node_id,)).fetchone()


def _complete_node(conn, node_id, provider, result):
    conn.execute(
        "UPDATE autoedit_nodes SET status='success', progress=100, provider=?, result_json=?, message=NULL, updated_at=?, finished_at=? WHERE id=?",
        (provider, json.dumps(result, ensure_ascii=False, default=str), _now(), _now(), node_id),
    )
    conn.commit()


def _fail_node(conn, node_id, message):
    conn.execute(
        "UPDATE autoedit_nodes SET status='failed', message=?, updated_at=?, finished_at=? WHERE id=?",
        (message[:2000], _now(), _now(), node_id),
    )
    conn.commit()


def _run_node(conn, node, work):
    """节点执行 + 复用"""
    if node["status"] == "success" and node["result_json"]:
        return json.loads(node["result_json"])
    conn.execute(
        "UPDATE autoedit_nodes SET status='processing', progress=20, attempt=attempt+CASE WHEN status='failed' THEN 1 ELSE 0 END, message=NULL, updated_at=? WHERE id=?",
        (_now(), node["id"]),
    )
    conn.commit()
    try:
        provider, result = work()
        _complete_node(conn, node["id"], provider, result)
        return result
    except Exception as e:
        _fail_node(conn, node["id"], str(e))
        raise


# ============ node workers ============

def _node_tts(conn, run_id, segment, work_dir):
    """TTS 节点: EdgeTTS 合成旁白"""
    from providers.tts import EdgeTTSProvider

    tts_text = (segment.get("subtitle") or segment.get("text") or "").strip() or "场景无字幕"
    input_data = {"text": tts_text, "voice": "zh-CN-XiaoxiaoNeural"}
    node = _ensure_node(conn, run_id, segment["id"], "tts", input_data)
    voice_path = work_dir / "voice.mp3"

    def work():
        result = EdgeTTSProvider().synthesize(tts_text, voice_path, voice="zh-CN-XiaoxiaoNeural")
        dur = _ffprobe_duration(voice_path)
        if dur:
            result["duration_seconds"] = dur
        return ("edge_tts", result)

    return _run_node(conn, node, work)


def _node_broll(conn, run_id, segment, work_dir, upload_duration):
    """B-roll 节点: 可选, 给长 kept segment 插入背景素材. MVP 默认跳过, 直接返回 None"""
    if not segment.get("asset_query") or segment.get("asset_kind") != "stock":
        # 不需要 B-roll
        return {"provider": "none", "local_path": None}
    if (segment["end_seconds"] - segment["start_seconds"]) < 5.0:
        # 短片段不调 B-roll
        return {"provider": "none", "local_path": None}

    input_data = {"query": segment["asset_query"]}
    node = _ensure_node(conn, run_id, segment["id"], "broll", input_data)
    broll_path = work_dir / "broll.mp4"

    def work():
        from providers.stock import fetch_with_fallback
        try:
            result = fetch_with_fallback(segment["asset_query"], broll_path)
            return (result["provider"], result)
        except Exception:
            # B-roll 失败非致命, fallback 到原视频
            return ("none", {"provider": "none", "local_path": None, "fallback": True})

    return _run_node(conn, node, work)


def _node_cut_segment(conn, run_id, segment, upload_path, voice_path, broll_path, work_dir, total_duration):
    """核心: ffmpeg 裁剪原视频 + 字幕烧入 + 旁白混合 -> segment.mp4"""
    input_data = {
        "segment_id": segment["id"],
        "start": segment["start_seconds"],
        "end": segment["end_seconds"],
        "subtitle": segment["subtitle"],
        "has_voice": bool(voice_path),
        "has_broll": bool(broll_path),
    }
    node = _ensure_node(conn, run_id, segment["id"], "cut", input_data)
    cut_path = work_dir / "cut.mp4"

    def work():
        seg_duration = max(0.5, segment["end_seconds"] - segment["start_seconds"])
        # 1. 写 srt 字幕 (兑底处理 None subtitle)
        srt_path = work_dir / "subtitle.srt"
        subtitle_text = (segment.get("subtitle") or segment.get("text") or "").strip() or " "
        _write_srt([{
            "start": 0.0,
            "end": seg_duration,
            "text": subtitle_text,
        }], srt_path)
        # srt path for ffmpeg subtitles filter (escape : and \\)
        srt_escaped = str(srt_path).replace("\\", "/").replace(":", "\\:")

        # 2. ffmpeg 裁剪 + 字幕烧入 + 旁白混合
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        cmd += ["-ss", str(segment["start_seconds"]), "-to", str(segment["end_seconds"]), "-i", str(upload_path)]
        if voice_path and Path(voice_path).exists():
            cmd += ["-i", str(voice_path)]
        # 字幕烧入: scale 到 1280:720 + 黑边
        vf = f"scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,subtitles='{srt_escaped}'"
        if voice_path and Path(voice_path).exists():
            # 有 voice: 视频静音原音, 旁白混合 (兑底处理: 原视频无音频流时仍能运行)
            af = "[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.0[voice]"
            # duration=first: 以视频时长为准
            cmd += ["-filter_complex", f"[0:v]{vf}[v];{af};[voice]anull[a]"]
            cmd += ["-map", "[v]", "-map", "[a]"]
        else:
            # 仅裁剪烧字幕, 保留原音 (原视频可能无音频流)
            cmd += ["-vf", vf]
            cmd += ["-map", "0:v", "-map", "0:a?"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p"]
        if voice_path and Path(voice_path).exists():
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += [str(cut_path)]

        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=180)
        if proc.returncode != 0:
            err_text = (proc.stderr or "").strip() or "(empty stderr)"
            raise RuntimeError(f"cut ffmpeg failed (rc={proc.returncode}): {err_text[-500:]}")
        if not cut_path.exists() or cut_path.stat().st_size < 1024:
            raise RuntimeError(f"cut output missing or empty: {cut_path}")
        return ("ffmpeg", {
            "local_path": str(cut_path),
            "duration_seconds": _ffprobe_duration(cut_path),
            "start_seconds": segment["start_seconds"],
            "end_seconds": segment["end_seconds"],
        })

    return _run_node(conn, node, work)


def _node_music(conn, run_id, work_dir):
    """背景音乐节点"""
    input_data = {"query": "calm cinematic background music"}
    node = _ensure_node(conn, run_id, None, "music", input_data)
    music_path = work_dir / "music.mp3"

    def work():
        from providers.music import FreesoundProvider
        if not os.getenv("FREESOUND_API_KEY"):
            return ("none", {"provider": "none", "local_path": None, "fallback": "no api key"})
        try:
            result = FreesoundProvider().fetch("calm cinematic background music", music_path)
            return ("freesound", result)
        except Exception as e:
            return ("none", {"provider": "none", "local_path": None, "fallback": str(e)[:200]})

    return _run_node(conn, node, work)


def _node_compose(conn, run_id, segments, segment_videos, music_path, work_dir, output_path):
    """最终拼接: ffmpeg concat 多个 segment + 音乐混音 -> final.mp4"""
    input_data = {
        "segment_count": len(segments),
        "has_music": bool(music_path),
        "output_path": str(output_path),
    }
    node = _ensure_node(conn, run_id, None, "compose", input_data)

    def work():
        # 1. 写 concat 列表
        concat_list = work_dir / "concat.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for sv in segment_videos:
                p = sv["local_path"].replace("\\", "/")
                f.write(f"file '{p}'\n")

        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "concat", "-safe", "0", "-i", str(concat_list)]
        if music_path and Path(music_path).exists():
            cmd += ["-i", str(music_path)]
            cmd += ["-filter_complex", "[0:a]volume=1.0[a0];[1:a]volume=0.12[music];[a0][music]amix=inputs=2:duration=first:dropout_transition=2[a]"]
            cmd += ["-map", "0:v", "-map", "[a]"]
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        else:
            cmd += ["-map", "0:v", "-map", "0:a?"]
            cmd += ["-c:a", "aac", "-b:a", "128k"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p"]
        cmd += ["-movflags", "+faststart"]
        cmd += [str(output_path)]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"compose ffmpeg failed: {proc.stderr.strip()[-500:]}")
        if not output_path.exists() or output_path.stat().st_size < 1024:
            raise RuntimeError(f"compose output missing or empty: {output_path}")
        dur = _ffprobe_duration(output_path)
        return ("ffmpeg", {
            "local_path": str(output_path),
            "duration_seconds": dur,
            "size_bytes": output_path.stat().st_size,
        })

    return _run_node(conn, node, work)


# ============ pipeline ============

def execute_pipeline(run_id, get_db):
    conn = get_db()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS autoedit_runs (
          id TEXT PRIMARY KEY, autoedit_draft_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued', progress INTEGER NOT NULL DEFAULT 0,
          render_job_id TEXT, message TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished_at TEXT
        );
        CREATE TABLE IF NOT EXISTS autoedit_nodes (
          id TEXT PRIMARY KEY, autoedit_run_id TEXT NOT NULL, segment_id TEXT, node_type TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued', progress INTEGER NOT NULL DEFAULT 0, provider TEXT,
          attempt INTEGER NOT NULL DEFAULT 1, input_json TEXT, result_json TEXT, message TEXT,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished_at TEXT
        );
        """)

        run = conn.execute("SELECT * FROM autoedit_runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            raise RuntimeError(f"Run {run_id} not found")

        conn.execute(
            "UPDATE autoedit_runs SET status='generating_assets', progress=5, updated_at=? WHERE id=?",
            (_now(), run_id),
        )
        conn.commit()

        draft = conn.execute(
            "SELECT * FROM autoedit_drafts WHERE id=?", (run["autoedit_draft_id"],)
        ).fetchone()
        if draft is None:
            raise RuntimeError("Draft not found")

        upload = conn.execute(
            "SELECT * FROM autoedit_uploads WHERE id=?", (draft["upload_id"],)
        ).fetchone()
        if upload is None:
            raise RuntimeError("Upload not found")

        segments = [
            dict(s) for s in conn.execute(
                "SELECT * FROM autoedit_segments WHERE autoedit_draft_id=? AND kind != 'drop' ORDER BY position",
                (draft["id"],),
            ).fetchall()
        ]
        if not segments:
            raise RuntimeError("No kept segments to render")

        run_dir = Path(__file__).parent / "data" / "output" / run_id
        _ensure_dir(run_dir)
        upload_path = Path(upload["stored_path"])

        segment_videos = []
        for idx, seg in enumerate(segments):
            seg_dir = run_dir / f"segment-{idx:03d}-{seg['id'][:8]}"
            _ensure_dir(seg_dir)

            # TTS
            voice_result = _node_tts(conn, run_id, seg, seg_dir)
            voice_path = seg_dir / "voice.mp3" if voice_result.get("local_path") else None

            # B-roll (可选, MVP 默认走 none)
            broll_result = _node_broll(conn, run_id, seg, seg_dir, upload["duration_seconds"])
            broll_path = seg_dir / "broll.mp4" if broll_result.get("local_path") else None

            # 裁剪 + 字幕 + 旁白
            cut_result = _node_cut_segment(
                conn, run_id, seg, upload_path, voice_path, broll_path, seg_dir, upload["duration_seconds"]
            )
            segment_videos.append({
                "segment_id": seg["id"],
                "local_path": cut_result["local_path"],
                "duration": cut_result["duration_seconds"],
            })

            progress = 5 + int(75 * (idx + 1) / len(segments))
            conn.execute(
                "UPDATE autoedit_runs SET progress=?, updated_at=? WHERE id=?",
                (progress, _now(), run_id),
            )
            conn.commit()

        # 音乐节点
        music_dir = run_dir / "music"
        _ensure_dir(music_dir)
        music_result = _node_music(conn, run_id, music_dir)
        music_path = music_dir / "music.mp3" if music_result.get("local_path") else None

        # 拼接
        final_path = run_dir / f"{run_id}.mp4"
        compose_result = _node_compose(conn, run_id, segments, segment_videos, music_path, run_dir, final_path)

        conn.execute(
            "UPDATE autoedit_runs SET status='success', progress=100, message=NULL, "
            "output_path=?, render_job_id=NULL, updated_at=?, finished_at=? WHERE id=?",
            (str(final_path), _now(), _now(), run_id),
        )
        conn.commit()
    except Exception as e:
        conn.execute(
            "UPDATE autoedit_runs SET status='failed', message=?, updated_at=?, finished_at=? WHERE id=?",
            (str(e)[:2000], _now(), _now(), run_id),
        )
        conn.commit()
    finally:
        conn.close()


# ============ router ============

def create_router(get_db):
    router = APIRouter(prefix="/autoedit-runs", tags=["autoedit-runs"])

    @router.post("/from-draft/{draft_id}")
    def create_run(draft_id: str, background_tasks: BackgroundTasks):
        conn = get_db()
        try:
            draft = conn.execute(
                "SELECT status FROM autoedit_drafts WHERE id=?", (draft_id,)
            ).fetchone()
            if draft is None:
                raise HTTPException(status_code=404, detail="Auto-edit draft not found")
            if draft["status"] != "confirmed":
                raise HTTPException(
                    status_code=409, detail="Confirm the draft before generation"
                )

            existing = conn.execute(
                "SELECT * FROM autoedit_runs WHERE autoedit_draft_id=? AND status IN ('queued','generating_assets','rendering','success') ORDER BY created_at DESC LIMIT 1",
                (draft_id,),
            ).fetchone()
            if existing:
                return _run_payload(conn, existing["id"])

            run_id = _run_id()
            ts = _now()
            conn.execute(
                "INSERT INTO autoedit_runs (id, autoedit_draft_id, status, progress, created_at, updated_at) "
                "VALUES (?, ?, 'queued', 0, ?, ?)",
                (run_id, draft_id, ts, ts),
            )
            conn.commit()
            background_tasks.add_task(execute_pipeline, run_id, get_db)
            return _run_payload(conn, run_id)
        finally:
            conn.close()

    @router.get("/{run_id}")
    def get_run(run_id: str):
        conn = get_db()
        try:
            return _run_payload(conn, run_id)
        finally:
            conn.close()

    @router.post("/{run_id}/retry")
    def retry_run(run_id: str, background_tasks: BackgroundTasks):
        conn = get_db()
        try:
            run = conn.execute(
                "SELECT * FROM autoedit_runs WHERE id=?", (run_id,)
            ).fetchone()
            if run is None:
                raise HTTPException(status_code=404, detail="Auto-edit run not found")
            if run["status"] != "failed":
                raise HTTPException(
                    status_code=409, detail="Only failed runs can be retried"
                )
            conn.execute(
                "UPDATE autoedit_runs SET status='queued', message=NULL, updated_at=?, finished_at=NULL WHERE id=?",
                (_now(), run_id),
            )
            conn.commit()
            background_tasks.add_task(execute_pipeline, run_id, get_db)
            return _run_payload(conn, run_id)
        finally:
            conn.close()

    return router