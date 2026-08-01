"""rev35 阶段 2 P0.6: render process manager.

Centralizes subprocess / progress / cancellation helpers + run_render_job entrypoint
that were inlined in main.py. Tests still access these via main.terminate_process_tree,
main.apply_worker_progress, main.mark_render_cancelled, main.expire_render_process,
main.run_render_job, main.ACTIVE_RENDER_PROCESSES - main.py re-exports them.
"""
import os
import platform
import re
import signal
import subprocess
import threading
import time
from pathlib import Path

import main  # used at call time so test patches on main.terminate_process_tree apply
from config import config
from db.connection import get_db

WORKER_SCRIPT = Path(__file__).parent / "remotion_runner.py"
ACTIVE_RENDER_PROCESSES = {}
ACTIVE_RENDER_LOCK = threading.Lock()

WORKER_PROGRESS_PATTERN = re.compile(r"^\[render-progress\]\s+(\d{1,3})$")


def apply_worker_progress(conn, job_id: str, output_line: str) -> bool:
    """rev24 stage B: parse '[render-progress] NN' from worker stdout, update render_jobs.progress.

    Returns True if the line matched a progress update and was applied; False otherwise.
    Status is held at 'processing' and progress monotonically non-decreasing.
    """
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


def terminate_process_tree(process) -> bool:
    """Kill the entire process tree of a Popen process (Windows: taskkill /T /F, POSIX: killpg SIGTERM)."""
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


def expire_render_process(process, timed_out: threading.Event) -> bool:
    """Set timed_out flag and kill the process tree; called by render timeout Timer.

    Looks up terminate_process_tree via main module at call time so tests patching
    main.terminate_process_tree still intercept this path.
    """
    timed_out.set()
    return main.terminate_process_tree(process)


def mark_render_cancelled(conn, job_id: str) -> bool:
    """Set status=failed with explicit 'Cancelled by user' message; only if still queued/processing."""
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


def run_render_job(job_id: str, props_path: str, resolution: str, extension: str, engine: str, renderer: str) -> None:
    """Execute a render_jobs row by spawning remotion_runner.py worker subprocess.

    Stages:
      1) status -> processing, reset progress 0
      2) branch on renderer: 'cloud' -> workers.cloud_renderer.run_cloud_render_job
      3) else spawn WORKER_SCRIPT as subprocess; track in ACTIVE_RENDER_PROCESSES
      4) start RENDER_TIMEOUT_SECONDS Timer to expire
      5) iterate stdout, apply_worker_progress on each line
      6) wait() + final state update: success (file/thumbnail populated), failed (tail of stderr)
    """
    with get_db() as conn:
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
