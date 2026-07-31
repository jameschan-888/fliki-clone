"""环境诊断 API: GET /env-check 返回完整诊断 JSON"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fastapi import APIRouter
from env_check import run_full_diagnostic, run_quick_diagnostic

def create_router():
    router = APIRouter(prefix="/env-check", tags=["env-check"])

    @router.get("")
    def full_check():
        return run_full_diagnostic()

    @router.get("/quick")
    def quick_check():
        """快速检查: 只返回 capabilities + warnings"""
        report = run_quick_diagnostic()
        return {
            "ok": True,
            "capabilities": report["capabilities"],
            "warnings": report["warnings"],
            "gpu_available": report["gpu"]["available"],
            "ffmpeg_available": report["ffmpeg"]["available"],
            "pytorch_installed": report["pytorch"]["installed"],
            "disk_free_gb": report["disk"]["free_gb"],
        }

    return router
