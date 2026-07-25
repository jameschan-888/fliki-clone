import json, os, time
"""环境诊断: 检测本机能力"""
import json, os, platform, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

def _safe_run(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if result.returncode != 0: return None
        return (result.stdout or b"").decode("utf-8", errors="replace").strip()
    except Exception: return None

def _safe_import(module_name):
    try:
        mod = __import__(module_name)
        return getattr(mod, "__version__", "unknown")
    except Exception: return None

def check_python():
    return {"version": platform.python_version(), "executable": sys.executable, "implementation": platform.python_implementation()}

def check_node():
    out = _safe_run(["node", "--version"])
    return {"version": out, "path": shutil.which("node")}

def check_ffmpeg():
    out = _safe_run(["ffmpeg", "-version"])
    if not out: return {"available": False}
    first = out.split(chr(10))[0]
    return {"available": True, "raw": first[:120]}

def check_ffprobe():
    out = _safe_run(["ffprobe", "-version"])
    if not out: return {"available": False}
    first = out.split(chr(10))[0]
    return {"available": True, "raw": first[:120]}

def check_disk(path=None):
    if path is None:
        path = os.getenv("FLIKI_DISK_PATH", "D:/workspace")
    try:
        usage = shutil.disk_usage(path)
        return {"path": path, "total_gb": round(usage.total/(1024**3),2), "free_gb": round(usage.free/(1024**3),2), "used_pct": round(usage.used/usage.total*100,1)}
    except Exception as e:
        return {"path": path, "error": str(e)[:200]}

def check_memory():
    if platform.system() == "Windows":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                return {"total_gb": round(stat.ullTotalPhys/(1024**3),2), "available_gb": round(stat.ullAvailPhys/(1024**3),2), "source": "ctypes"}
        except Exception: pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return {"total_gb": round(kb/(1024**2),2), "source": "/proc/meminfo"}
    except Exception: pass
    return {"total_gb": None, "source": "unavailable"}

def check_cpu():
    return {"cores_logical": os.cpu_count() or 0, "machine": platform.machine(), "system": platform.system()}

def check_gpu():
    result = {"available": False, "vendor": None, "model": None, "vram_gb": None, "cuda_available": False}
    nvidia_out = _safe_run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    if nvidia_out:
        parts = [p.strip() for p in nvidia_out.split(",")]
        result["available"] = True
        result["vendor"] = "NVIDIA"
        result["model"] = parts[0] if parts else None
        if len(parts) > 1:
            try: result["vram_gb"] = round(int(parts[1])/1024, 2)
            except ValueError: pass
        result["cuda_available"] = True
        return result
    if platform.system() == "Windows":
        ps_cmd = "(Get-CimInstance Win32_VideoController).Name"
        out = _safe_run(["powershell", "-NoProfile", "-Command", ps_cmd], timeout=8)
        if out:
            result["available"] = True
            result["model"] = out.split(chr(10))[0].strip()
            if "NVIDIA" in out:
                result["vendor"] = "NVIDIA"
                result["cuda_available"] = True
            elif "AMD" in out or "Radeon" in out: result["vendor"] = "AMD"
            elif "Intel" in out: result["vendor"] = "Intel"
            return result
    return result

def check_pytorch():
    out = {"installed": False, "version": None, "cuda_available": False, "device_count": 0}
    try:
        import torch
        out["installed"] = True
        out["version"] = torch.__version__
        out["cuda_available"] = torch.cuda.is_available()
        if out["cuda_available"]: out["device_count"] = torch.cuda.device_count()
    except ImportError: pass
    return out

def check_python_packages():
    packages = ["fastapi", "uvicorn", "pydantic", "edge_tts", "faster_whisper", "whisper", "httpx", "torch", "onnxruntime", "numpy", "PIL"]
    result = {}
    for pkg in packages:
        v = _safe_import(pkg)
        if v: result[pkg] = v
    return result

def check_workspace():
    workspace = Path("D:/workspace/Fliki视频制作还原")
    if not workspace.exists():
        workspace = Path(__file__).resolve().parents[1]
    return {"path": str(workspace), "exists": workspace.exists(),
            "backend_dir_exists": (workspace / "backend").exists(),
            "app_dir_exists": (workspace / "app").exists(),
            "data_dir_exists": (workspace / "backend" / "data").exists()}

def check_render_capability(gpu_info, pytorch_info):
    caps = {"edge_tts": True, "faster_whisper": True, "wav2lip_onnx": True, "remotion_render": True, "autoedit_pipeline": True, "sadtalker": False, "musetalk": False, "gpt_sovits_cpu": True, "gpt_sovits_gpu": False, "heygen_api": True}
    if gpu_info.get("available") and gpu_info.get("vendor") == "NVIDIA" and pytorch_info.get("cuda_available"):
        caps["sadtalker"] = True
        caps["musetalk"] = True
        caps["gpt_sovits_gpu"] = True
    return caps

def check_gpt_sovits():
    """Probe user-configured GPT-SoVITS endpoint (P5D-3). Never raises; safe offline."""
    configured_url = os.getenv("FLIKI_GPT_SOVITS_URL") or "http://127.0.0.1:9880"
    out = {"configured_url": configured_url, "available": False, "latency_ms": None, "http_status": None, "error": None}
    try:
        import httpx
        started = time.time()
        response = httpx.get(configured_url.rstrip("/") + "/", timeout=5.0)
        out["latency_ms"] = int((time.time() - started) * 1000)
        out["http_status"] = response.status_code
        out["available"] = response.status_code < 500
        if not out["available"]:
            out["error"] = f"HTTP {response.status_code}"
    except Exception as exc:
        out["error"] = str(exc)
    return out
def check_wav2lip_onnx():
    """Probe whether local Wav2Lip-ONNX can run on this machine (P5E).
    Never raises. Returns a structured dict so the env-check UI can render it.
    """
    out = {"provider": "wav2lip_onnx", "ok": False, "ffmpeg_available": False,
           "model_present": False, "dependencies_ok": False,
           "dependency_warnings": [], "latency_ms": None, "error": None}
    started = time.time()
    env_path = os.getenv("FLIKI_WAV2LIP_MODEL", "data/models/wav2lip_onnx/wav2lip.onnx")
    out["configured_path"] = env_path
    try:
        candidate = Path(env_path)
        if not candidate.is_absolute():
            candidate = Path(__file__).resolve().parent / candidate
        out["resolved_path"] = str(candidate)
        out["model_present"] = candidate.is_file()
    except Exception as exc:
        out["dependency_warnings"].append(f"model_path: {exc}")
    for mod_name in ("cv2", "librosa", "onnxruntime", "numpy"):
        try:
            __import__(mod_name)
        except Exception as exc:
            out["dependency_warnings"].append(f"{mod_name}: {type(exc).__name__}")
    out["dependencies_ok"] = not out["dependency_warnings"]
    try:
        import shutil
        out["ffmpeg_available"] = bool(shutil.which("ffmpeg"))
    except Exception:
        pass
    out["latency_ms"] = int((time.time() - started) * 1000)
    out["ok"] = (out["ffmpeg_available"] and out["dependencies_ok"]) or out["model_present"]
    out["error"] = None if out["ok"] else "Missing dependencies or model; will fall back to static_avatar MP4"
    return out


def build_capability_groups(provider_configs, *, ffmpeg_available, gpt_sovits_info, wav2lip_info, capabilities):
    """借鉴灵剪 packages/core/capabilities.py detect_capabilities 输出。

    按 kind 分组，每组包含 providers[]（含 is_mock / available / latency_ms）。
    返回 {"publish_grade": bool, "groups": [...]}
    """
    groups = []
    for category in ("text", "stock", "tts", "music", "avatar"):
        rows = [row for row in provider_configs if row["category"] == category]
        providers = []
        for row in rows:
            cfg = {}
            try:
                import json as _json
                cfg = _json.loads(row["config_json"] or "{}")
            except Exception:
                cfg = {}
            is_mock = bool(cfg.get("is_mock", False))
            available = bool(row["enabled"])
            latency_ms = None
            kind_hint = "mock 仅用于本地预览 / 测试，不能 release"
            if category == "tts" and row["name"] == "edge_tts":
                kind_hint = "edge-tts 本地依赖即可运行，免费"
            elif category == "tts" and row["name"] == "gpt_sovits":
                latency_ms = (gpt_sovits_info or {}).get("latency_ms")
                available = available and bool((gpt_sovits_info or {}).get("available"))
                kind_hint = "需外部 HTTP 服务在 " + str((gpt_sovits_info or {}).get("configured_url", "http://127.0.0.1:9880"))
            elif category == "stock" and row["name"] in ("pexels", "pixabay"):
                env_name = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}.get(row["name"])
                import os
                available = available and bool(os.getenv(env_name, ""))
                kind_hint = "免费 API；按 key 区分"
            elif category == "music" and row["name"] == "freesound":
                import os
                available = available and bool(os.getenv("FREESOUND_API_KEY", ""))
                kind_hint = "按授权下载；无 key 退化为 silence"
            elif category == "avatar" and row["name"] == "wav2lip_onnx":
                available = available and bool((wav2lip_info or {}).get("ok"))
                latency_ms = (wav2lip_info or {}).get("latency_ms")
                kind_hint = "需本地 onnx 模型；缺失自动 fallback static_avatar"
            providers.append({
                "name": row["name"],
                "is_mock": is_mock,
                "available": available,
                "is_default": bool(row["is_default"]),
                "priority": row["priority"],
                "latency_ms": latency_ms,
                "hint": kind_hint,
            })
        default_provider = next((p for p in providers if p["is_default"]), None)
        publish_grade = bool(default_provider and default_provider["available"] and not default_provider["is_mock"])
        groups.append({
            "kind": category,
            "publish_grade": publish_grade,
            "providers": providers,
            "default": (default_provider or {}).get("name"),
        })
    return {"publish_grade": all(g["publish_grade"] for g in groups), "groups": groups}


def run_full_diagnostic():
    gpu = check_gpu()
    pytorch = check_pytorch()
    provider_configs = []
    try:
        import sqlite3
        from config import config as _config
        conn = sqlite3.connect(_config["DB_PATH"])
        conn.row_factory = sqlite3.Row
        try:
            from provider_config import seed_runtime_providers
            seed_runtime_providers(conn)
            provider_configs = conn.execute("SELECT category, name, enabled, is_default, priority, config_json FROM provider_configs ORDER BY category, priority, name").fetchall()
        finally:
            conn.close()
    except Exception:
        provider_configs = []
    gpt_info = check_gpt_sovits()
    wav_info = check_wav2lip_onnx()
    capability_groups = build_capability_groups(provider_configs, ffmpeg_available=check_ffmpeg().get("available", False), gpt_sovits_info=gpt_info, wav2lip_info=wav_info, capabilities=check_render_capability(gpu, pytorch))
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "python": check_python(), "node": check_node(), "ffmpeg": check_ffmpeg(), "ffprobe": check_ffprobe(), "cpu": check_cpu(), "memory": check_memory(), "disk": check_disk(), "gpu": gpu, "pytorch": pytorch, "python_packages": check_python_packages(), "workspace": check_workspace(), "gpt_sovits": gpt_info, "wav2lip_onnx": wav_info, "capabilities": check_render_capability(gpu, pytorch), "capability_groups": capability_groups}
    warnings = []
    if not gpu.get("available"):
        warnings.append({"level": "info", "msg": "未检测到 GPU, SadTalker/MuseTalk 不可用, 建议 Wav2Lip-ONNX"})
    elif gpu.get("vendor") != "NVIDIA":
        warnings.append({"level": "warning", "msg": "检测到 " + str(gpu.get("vendor")) + " GPU, SadTalker/MuseTalk 需 NVIDIA + CUDA"})
    if report["disk"]["free_gb"] < 10:
        warnings.append({"level": "warning", "msg": "D 盘仅剩 " + str(report["disk"]["free_gb"]) + " GB, 模型下载可能失败"})
    if not report["ffmpeg"]["available"]:
        warnings.append({"level": "error", "msg": "ffmpeg 未安装, Auto-edit/Render 不可用"})
    if not pytorch.get("installed"):
        warnings.append({"level": "info", "msg": "PyTorch 未安装, 数字人和声音克隆不可用"})
    report["warnings"] = warnings
    return report

if __name__ == "__main__":
    print(json.dumps(run_full_diagnostic(), ensure_ascii=False, indent=2))
