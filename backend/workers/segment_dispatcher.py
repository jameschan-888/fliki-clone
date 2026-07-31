"""Render segment parallel dispatcher (rev17)."""
import importlib.util, json, os, shutil, subprocess, sys, time, uuid, threading
from pathlib import Path

SEGMENT_SCENES = max(1, int(os.environ.get("RENDER_SEGMENT_SCENES", "10")))  # rev17b: 10 场景/段, 30 场景视频 K=3
POLL_INTERVAL = max(1, int(os.environ.get("RENDER_CONCAT_POLL_INTERVAL", "5")))
POLL_TIMEOUT = max(60, int(os.environ.get("RENDER_CONCAT_TIMEOUT", "5400")))
ACQUIRE_TIMEOUT = max(60, int(os.environ.get("RENDER_SEGMENT_ACQUIRE_TIMEOUT", "1800")))
FFMPEG_BIN = os.environ.get("FFMPEG_CONCAT_BIN", "ffmpeg")
RENDER_PROVIDER = os.environ.get("RENDER_PROVIDER", "local")  # rev18: local | cloud


def split_scenes(scenes, seg_size):
    out = []
    n = len(scenes)
    for i in range(0, n, seg_size):
        j = min(n, i + seg_size)
        out.append((i, j, scenes[i:j]))
    return out


def write_segment_props(base_props, subset, segment_dir, start_idx, seg_idx):
    duration = sum((s.get("durationInSeconds") or 0) for s in subset)
    seg = dict(base_props)
    seg["scenes"] = subset
    seg["durationInSeconds"] = duration
    seg["_segmentIndex"] = seg_idx
    seg["_segmentStartIdx"] = start_idx
    seg["_publicDir"] = base_props.get("_publicDir", str(segment_dir / "remotion_public"))
    p = segment_dir / ("seg_" + str(seg_idx) + "_props.json")
    p.write_text(json.dumps(seg, ensure_ascii=False), encoding="utf-8")
    return p


def ffmpeg_concat(segment_files, output_path):
    if not segment_files:
        return False, "no segments"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_txt = output_path.parent / "concat_list.txt"
    with open(list_txt, "w", encoding="utf-8") as fp:
        for f in segment_files:
            fp.write("file '" + str(f.resolve()) + "'" + chr(10))
    try:
        proc = subprocess.run(
            [FFMPEG_BIN, "-y", "-f", "concat", "-safe", "0", "-i", str(list_txt),
             "-c", "copy", str(output_path)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return False, "ffmpeg rc=" + str(proc.returncode) + " stderr=" + proc.stderr[-300:]
        return True, ""
    except FileNotFoundError:
        return False, "ffmpeg not found"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg concat timeout"


def make_thumbnails(final_mp4, run_dir):
    thumb = run_dir / "concat_thumb.jpg"
    preview = run_dir / "concat_thumbPreview.jpg"
    try:
        subprocess.run([FFMPEG_BIN, "-y", "-ss", "0.5", "-i", str(final_mp4),
                        "-frames:v", "1", "-q:v", "2", str(thumb)],
                       capture_output=True, timeout=30, check=True)
        subprocess.run([FFMPEG_BIN, "-y", "-i", str(thumb),
                        "-vf", "scale=320:-2", "-frames:v", "1", "-q:v", "3", str(preview)],
                       capture_output=True, timeout=30, check=True)
    except Exception:
        return None, None
    return thumb, preview


def poll_segments(connection, run_id, segment_job_ids, segment_dir):
    deadline = time.time() + POLL_TIMEOUT
    segment_files = []
    for i in range(len(segment_job_ids)):
        segment_files.append(segment_dir / ("seg_" + str(i) + ".mp4"))
    while time.time() < deadline:
        states = []
        for jid in segment_job_ids:
            row = connection.execute(
                "SELECT status, progress, message FROM render_jobs WHERE _id=?", (jid,)
            ).fetchone()
            states.append({
                "status": row["status"] if row else "missing",
                "progress": row["progress"] if row else 0,
                "message": row["message"] if row else "",
            })
        if all(s["status"] in ("success", "failed", "missing") for s in states):
            failed = [s for s in states if s["status"] != "success"]
            if failed:
                msg = "; ".join(s["message"] for s in failed if s.get("message"))
                return False, msg[:2000], []
            try:
                from config import OUTPUT_DIR as OR
            except Exception:
                OR = segment_dir
            for i, jid in enumerate(segment_job_ids):
                row = connection.execute(
                    "SELECT file FROM render_jobs WHERE _id=?", (jid,)
                ).fetchone()
                src = None
                # Try 4 candidate paths for renderer output (rev18 cloud + local)
                if row and row["file"]:
                    cand = Path(row["file"])
                    if not cand.is_absolute():
                        cand = Path(OR) / cand
                    if cand.exists():
                        src = cand
                if src is None:
                    cand = Path(OR) / jid / (jid + ".mp4")
                    if cand.exists():
                        src = cand
                if src is None:
                    # cloud renderer writes to OUTPUT_DIR/jid.mp4 (flat)
                    cand = Path(OR) / (jid + ".mp4")
                    if cand.exists():
                        src = cand
                if src is None:
                    # cloud renderer nested fallback
                    cand = Path(OR) / jid / jid / (jid + ".mp4")
                    if cand.exists():
                        src = cand
                if src:
                    try:
                        shutil.copy2(src, segment_files[i])
                    except OSError:
                        pass
            return True, "", segment_files
        avg = int(sum(s["progress"] or 0 for s in states) / max(1, len(states)))
        try:
            connection.execute(
                "UPDATE workflow_runs SET progress=?, message=?, updated_at=? WHERE id=?",
                (75 + int(avg * 0.2),
                 "seg " + ",".join((s["status"] or "?")[:4] for s in states),
                 time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                 run_id),
            )
            connection.commit()
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return False, "segment poll timeout " + str(POLL_TIMEOUT) + "s", []


def _ensure_main_loaded():
    """Ensure main module is available with run_render_job."""
    if "main" in sys.modules:
        return sys.modules["main"]
    try:
        spec = importlib.util.spec_from_file_location(
            "main", Path(__file__).parent.parent / "main.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["main"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print("[seg-dispatcher] main import failed:", e)
        return None



def _needs_chrome_slot(renderer):
    """True when the renderer still needs a local Chrome process."""
    force = (os.environ.get("RENDER_FORCE_CHROME_SLOT", "") or "").lower()
    if force in ("1", "true", "yes"):
        return True
    if force in ("0", "false", "no"):
        return False
    return renderer not in ("cloud", "lambda", "mock")


def ffmpeg_concat_with_retry(segment_files, output_path, retries=2, timeout=180):
    """Bounded-retry ffmpeg concat (handles transient file locks)."""
    last_err = ""
    for attempt in range(retries + 1):
        ok, msg = ffmpeg_concat(segment_files, output_path)
        if ok:
            return True, ""
        last_err = msg
        if attempt < retries:
            time.sleep(1)
    return False, last_err


def _run_segment(jid, props_path, resolution, renderer):
    """Dispatch a single segment render with provider-aware concurrency."""
    if _needs_chrome_slot(renderer):
        from workers.render_queue import render_slot
        with render_slot(jid, timeout=ACQUIRE_TIMEOUT):
            run_render_job(jid, str(props_path), resolution, "mp4", "chrome", renderer)
    else:
        # Cloud/Lambda: no local Chrome, no semaphore.
        run_render_job(jid, str(props_path), resolution, "mp4", "chrome", renderer)


def dispatch_segments(connection, run_id, scenes, base_props, run_dir, resolution, renderer=None, max_concurrent=None):
    """Split scenes into K segments, render in parallel, concat with ffmpeg.

    rev24 stage C additions:
    - cloud/lambda providers skip the local Chrome render slot
    - max_concurrent throttles segment fan-out (default K, env override)
    - ffmpeg concat retries on transient file locks
    """
    n = len(scenes)
    if n == 0:
        return False, "no scenes", ""
    if renderer is None:
        renderer = RENDER_PROVIDER
    pieces = split_scenes(scenes, SEGMENT_SCENES)
    k = len(pieces)
    seg_dir = run_dir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    main_mod = _ensure_main_loaded()
    if main_mod is None or not hasattr(main_mod, "run_render_job"):
        return False, "main.run_render_job not available", ""
    global run_render_job
    run_render_job = main_mod.run_render_job
    job_ids = []
    props_paths = []
    for idx, (start, end, subset) in enumerate(pieces):
        props_path = write_segment_props(base_props, subset, seg_dir, start, idx)
        cid = run_id + "-s" + str(idx) + uuid.uuid4().hex[:8]
        now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        try:
            connection.execute(
                "INSERT INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, "workflow-" + run_id + "-seg-" + str(idx), "queued", 0, resolution, "mp4", renderer, "remotion", now_ts),
            )
            connection.commit()
        except Exception as e:
            return False, "render_jobs insert seg " + str(idx) + ": " + str(e), ""
        job_ids.append(cid)
        props_paths.append(props_path)

    if max_concurrent is None:
        env_cap = (os.environ.get("RENDER_SEGMENT_MAX_CONCURRENT", "") or "").strip()
        if env_cap:
            try:
                max_concurrent = max(1, int(env_cap))
            except ValueError:
                max_concurrent = k
        else:
            max_concurrent = k

    _sem = threading.BoundedSemaphore(max_concurrent)

    def _run_seg(jid, pp):
        try:
            _sem.acquire()
            try:
                _run_segment(jid, pp, resolution, renderer)
            finally:
                _sem.release()
        except Exception as e:
            print("[seg-dispatcher] seg worker crashed:", jid, str(e))

    threads = []
    for jid, pp in zip(job_ids, props_paths):
        t = threading.Thread(target=_run_seg, args=(jid, pp), daemon=True)
        t.start()
        threads.append(t)

    ok, msg, seg_files = poll_segments(connection, run_id, job_ids, seg_dir)
    if not ok:
        return False, msg, ""
    final_mp4 = run_dir / "concat.mp4"
    ok2, msg2 = ffmpeg_concat_with_retry(seg_files, final_mp4)
    if not ok2:
        return False, "concat: " + msg2, ""
    thumb, preview = make_thumbnails(final_mp4, run_dir)
    cid_final = run_id + "-concat"
    now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        from config import OUTPUT_DIR
        rel_path = str(final_mp4.relative_to(Path(OUTPUT_DIR)))
        thumb_rel = str(thumb.relative_to(Path(OUTPUT_DIR))) if thumb else None
        prev_rel = str(preview.relative_to(Path(OUTPUT_DIR))) if preview else None
    except Exception:
        rel_path = str(final_mp4)
        thumb_rel = None
        prev_rel = None
    try:
        connection.execute(
            "INSERT OR REPLACE INTO render_jobs (_id, playback_id, status, progress, resolution, extension, renderer, engine, file, thumbnail, thumbnail_preview, media_generated_id, finished_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (cid_final, "workflow-" + run_id, "success", 100, resolution, "mp4",
             renderer, "remotion", rel_path, thumb_rel, prev_rel, cid_final, now_ts, now_ts),
        )
        connection.commit()
    except Exception as e:
        return True, "concat ok but insert failed: " + str(e), cid_final
    return True, "segments=" + str(k), cid_final