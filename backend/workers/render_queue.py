"""Render task queue (rev18 stage C).

Limits concurrent render processes to prevent chrome OOM across multiple
drafts. Implements a simple semaphore + SQLite-backed pending queue.

Design:
- `acquire_slot(job_id)` blocks until a slot is free (returns True if acquired)
- `release_slot(job_id)` marks slot free
- `MAX_CONCURRENT` env (default 3) caps parallel chrome render processes
- `ACTIVE_RENDER_LOCK` from main.py is the canonical source of truth

For multi-draft scenarios:
- N drafts each request render
- Queue accepts up to MAX_CONCURRENT, others wait
- Per-segment dispatcher (rev17) plus this queue = bounded concurrency
"""
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

MAX_CONCURRENT = max(1, int(os.environ.get("RENDER_QUEUE_MAX_CONCURRENT", "3")))
ACQUIRE_TIMEOUT = max(60, int(os.environ.get("RENDER_QUEUE_ACQUIRE_TIMEOUT", "1800")))

_QUEUE_LOCK = threading.Lock()
_QUEUE_SEMAPHORE = threading.Semaphore(MAX_CONCURRENT)
_ACTIVE_SLOTS = {}  # job_id -> acquired_at
_QUEUE_DB = None


def _get_db():
    global _QUEUE_DB
    if _QUEUE_DB is None:
        from config import OUTPUT_DIR as OUT
        db_path = Path(OUT).parent / "render_queue.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _QUEUE_DB = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30)
        _QUEUE_DB.execute(
            "CREATE TABLE IF NOT EXISTS render_queue (_id TEXT PRIMARY KEY, status TEXT, "
            "started_at TEXT, finished_at TEXT, message TEXT)"
        )
        _QUEUE_DB.commit()
    return _QUEUE_DB


def acquire_slot(job_id, timeout=None):
    """Acquire a render slot. Returns (ok: bool, message: str)."""
    timeout = timeout if timeout is not None else ACQUIRE_TIMEOUT
    deadline = time.time() + timeout
    while time.time() < deadline:
        acquired = _QUEUE_SEMAPHORE.acquire(timeout=min(10, max(1, int(deadline - time.time()))))
        if acquired:
            with _QUEUE_LOCK:
                _ACTIVE_SLOTS[job_id] = time.time()
            try:
                db = _get_db()
                now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                db.execute(
                    "INSERT OR REPLACE INTO render_queue (_id, status, started_at) VALUES (?, ?, ?)",
                    (job_id, "running", now),
                )
                db.commit()
            except Exception:
                pass
            return True, "slot acquired"
        time.sleep(1)
    return False, "queue acquire timeout after " + str(timeout) + "s"


def release_slot(job_id, message=""):
    """Release a render slot."""
    with _QUEUE_LOCK:
        _ACTIVE_SLOTS.pop(job_id, None)
    _QUEUE_SEMAPHORE.release()
    try:
        db = _get_db()
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        db.execute(
            "UPDATE render_queue SET status=?, finished_at=?, message=? WHERE _id=?",
            ("released", now, message, job_id),
        )
        db.commit()
    except Exception:
        pass


def get_active_count():
    with _QUEUE_LOCK:
        return len(_ACTIVE_SLOTS)


def get_queue_stats():
    try:
        db = _get_db()
        cur = db.execute(
            "SELECT status, COUNT(*) FROM render_queue GROUP BY status"
        )
        return {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        return {}


@contextmanager
def render_slot(job_id, timeout=None):
    """Context manager: acquire + auto-release on exit."""
    ok, msg = acquire_slot(job_id, timeout=timeout)
    if not ok:
        raise RuntimeError("render_queue: " + msg)
    try:
        yield
    finally:
        release_slot(job_id, "context exit")
