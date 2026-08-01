"""rev35 阶段 2 P0.2: startup/health/root + 启动诊断.

P0 系列进程: 把 main.py 的 startup helper 三件 + 3 个 inline 路由
(/startup-status, /health, /) 抽到独立 router 模块. 内部使用 main.py lifespan
启动同一个后台诊断线程, 通过 from main import 避免循环 (main.py 在 include_router
之前已定义 _background_diagnostic)."""

import os
import platform
import shutil
import time
import json
from pathlib import Path

from fastapi import APIRouter, Request

from db.connection import get_db
from config import config

router = APIRouter(tags=["meta"])

START_TIME = time.time()

_startup_diagnostic_status = {"state": "pending", "finished_at": None, "error": None}


def write_startup_diagnostic():
    """rev24 P1-B: 写 startup 诊断报告到 env-check.json + 返回 report."""
    try:
        from env_check import run_full_diagnostic
        report = run_full_diagnostic()
        report_path = Path(config["DATA_DIR"]) / "env-check.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        for warning in report.get("warnings", []):
            level = warning.get("level", "info")
            msg = warning.get("msg", "")
            print("[env-check] " + str(level).upper() + ": " + str(msg))
        return report
    except Exception as error:
        print("[env-check] WARNING: startup diagnostic failed: " + str(error))
        return {"error": str(error)}

import threading


def _diagnose_sync():
    """同步执行 write_startup_diagnostic + 更新 _startup_diagnostic_status. 测试也调用本函数."""
    try:
        report = write_startup_diagnostic()
        _startup_diagnostic_status["state"] = "ready" if not (report or {}).get("error") else "error"
        _startup_diagnostic_status["error"] = (report or {}).get("error")
    except Exception as error:
        _startup_diagnostic_status["state"] = "error"
        _startup_diagnostic_status["error"] = str(error)
    finally:
        _startup_diagnostic_status["finished_at"] = int(time.time())


def run_startup_diagnostic_background():
    """rev24 P1-B: 启动后台线程跑 _diagnose_sync, 不阻塞 lifespan yield."""
    threading.Thread(target=_diagnose_sync, name="env-diagnostic", daemon=True).start()



@router.get("/startup-status")
def startup_status():
    return _startup_diagnostic_status


@router.get("/health")
def health():
    """rev24 阶段 D P1-C 收口: liveness + 资源健康 (cpu / disk / queue)."""
    try:
        du = shutil.disk_usage(str(Path(config["DATA_DIR"])))
        disk_free_gb = round(du.free / 1e9, 2)
        disk_total_gb = round(du.total / 1e9, 2)
    except Exception:
        disk_free_gb = None
        disk_total_gb = None
    queued = active = None
    try:
        from workers.render_queue import get_active_count, get_queue_stats
        active = int(get_active_count())
        stats = get_queue_stats() or {}
        queued = int(stats.get("queued", 0))
    except Exception:
        pass
    try:
        from env_check import _FULL_DIAG_CACHE
        _cached_ts = _FULL_DIAG_CACHE.get("ts", 0) or 0
        cache_age = round(time.time() - _cached_ts, 1) if _cached_ts > 0 else None
        cached = bool(_FULL_DIAG_CACHE.get("result"))
    except Exception:
        cache_age = None
        cached = False
    return {
        "status": "ok",
        "ts": int(time.time()),
        "version": getattr(__import__("__main__"), "__version__", "0.0.0"),
        "python_version": platform.python_version(),
        "uptime_seconds": int(time.time() - START_TIME),
        "cpu_count": os.cpu_count(),
        "disk_free_gb": disk_free_gb,
        "disk_total_gb": disk_total_gb,
        "render_queue": {"queued": queued, "active": active},
        "env_check_cache": {"cached": cached, "age_seconds": cache_age},
    }


@router.get("/")
def root(request: Request):
    return {"api": "fliki-clone", "version": request.app.version, "endpoints": [
        "/health", "/styles", "/media-samples",
        "/render.latest", "/render.create", "/providers"
    ]}