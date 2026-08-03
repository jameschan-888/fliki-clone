import json, os, time
from concurrent.futures import ThreadPoolExecutor
import httpx
"""环境诊断: 检测本机能力"""
import json, os, platform, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone

def _safe_run(cmd, timeout=3):
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode != 0: return None
        return (result.stdout or b"").decode("utf-8", errors="replace").strip()
    except Exception: return None

# rev33: 完整诊断缓存 (30s TTL), 避免每次刷新卡 minimax probes 60s+
_FULL_DIAG_CACHE = {"ts": 0.0, "result": None}
_FULL_DIAG_TTL_SEC = 30.0

# rev33: 完整诊断缓存 (30s TTL), 避免每次刷新卡 minimax probes
_FULL_DIAG_CACHE = {"ts": 0.0, "result": None}
_FULL_DIAG_TTL_SEC = 30.0

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
    nvidia_out = _safe_run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], timeout=1)
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
        powershell = shutil.which("powershell") or shutil.which("pwsh")
        out = _safe_run([powershell, "-NoProfile", "-Command", ps_cmd], timeout=3) if powershell else None
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

def check_external_provider(name, env_key, base_url, timeout=5.0):
    """轻量探活: GET base_url, 返回 status / latency / error. 全部 mock 测试, 不真连外网."""
    out = {"provider": name, "env_key": env_key, "base_url": base_url, "configured_url": base_url, "available": False, "latency_ms": None, "http_status": None, "error": None}
    try:
        import httpx
        started = time.time()
        response = httpx.get(base_url, timeout=timeout)
        out["latency_ms"] = int((time.time() - started) * 1000)
        out["http_status"] = response.status_code
        out["available"] = response.status_code < 500
        if not out["available"]:
            out["error"] = f"HTTP {response.status_code}"
    except Exception as exc:
        out["error"] = str(exc)[:200]
    return out


def check_stock_providers():
    """P6B: 用轻量探活检测 Pexels / Pixabay / Freesound 是否能连 (mock 友好).
    真实调用见 providers.stock.fetch_with_fallback / providers.music.FreesoundProvider.fetch."
    """
    return {
        "pexels": check_external_provider("pexels", "PEXELS_API_KEY", "https://api.pexels.com/videos/search"),
        "pixabay": check_external_provider("pixabay", "PIXABAY_API_KEY", "https://pixabay.com/api/videos/"),
        "freesound": check_external_provider("freesound", "FREESOUND_API_KEY", "https://freesound.org/apiv2/search/text/"),
    }


def check_gpt_sovits():
    """Probe user-configured GPT-SoVITS endpoint (P5D-3). Never raises; safe offline."""
    configured_url = os.getenv("FLIKI_GPT_SOVITS_URL") or "http://127.0.0.1:9880"
    return check_external_provider("gpt_sovits", "FLIKI_GPT_SOVITS_URL", configured_url.rstrip("/") + "/")


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
            elif category == "stock" and cfg.get("is_pro_video"):
                env_name = cfg.get("api_key_env", "")
                available = available and bool(os.getenv(env_name, "")) if env_name else available
                kind_hint = "新一代视频生成模型 (fliki 同代), 需 API key: " + (env_name or "未配置")
            elif category == "stock" and cfg.get("is_pro_image"):
                env_name = cfg.get("api_key_env", "")
                available = available and bool(os.getenv(env_name, "")) if env_name else available
                kind_hint = "新一代图像生成模型 (fliki 同代), 需 API key: " + (env_name or "未配置")
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


def check_wav2lip_onnx():
    """Probe whether local Wav2Lip-ONNX can run on this machine (P5E).
    Never raises. Returns a structured dict so the env-check UI can render it.
    """
    out = {"provider": "wav2lip_onnx", "ok": False, "ffmpeg_available": False,
           "model_present": False, "dependencies_ok": False,
           "dependency_warnings": [], "latency_ms": None, "error": None,
           "alias_used": None}
    started = time.time()
    env_path = os.getenv("FLIKI_WAV2LIP_MODEL", "data/models/wav2lip/wav2lip.onnx")
    out["configured_path"] = env_path
    candidate = Path(env_path)
    if not candidate.is_absolute():
        candidate = Path(__file__).resolve().parent / candidate
    out["resolved_path"] = str(candidate)
    if candidate.is_file():
        out["model_present"] = True
    if not out["model_present"]:
        for alt in (
            Path(__file__).resolve().parent / "data" / "models" / "wav2lip_onnx" / "wav2lip.onnx",
            Path(__file__).resolve().parent / "data" / "wav2lip" / "wav2lip.onnx",
        ):
            if alt.is_file():
                out["model_present"] = True
                out["resolved_path"] = str(alt)
                out["alias_used"] = str(alt.parent.name + "/wav2lip.onnx")
                break
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

def run_quick_diagnostic():
    """Fast, local-only startup/UI check. Never calls external providers."""
    gpu = check_gpu()
    pytorch = check_pytorch()
    ffmpeg = check_ffmpeg()
    disk = check_disk()
    capabilities = check_render_capability(gpu, pytorch)
    warnings = []
    if not ffmpeg.get("available"):
        warnings.append({"level": "error", "msg": "FFmpeg 不可用，本地渲染会失败"})
    if not gpu.get("cuda_available"):
        warnings.append({"level": "info", "msg": "当前使用 CPU/Intel GPU，已采用低资源本地渲染配置"})
    if disk.get("free_gb") is not None and disk["free_gb"] < 10:
        warnings.append({"level": "warning", "msg": "D 盘剩余空间低于 10GB"})
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gpu": gpu,
        "pytorch": pytorch,
        "ffmpeg": ffmpeg,
        "disk": disk,
        "capabilities": capabilities,
        "warnings": warnings,
    }


def run_full_diagnostic():
    # rev33: 30s TTL 缓存; 频繁刷新场景秒回
    _now = time.time()
    if _FULL_DIAG_CACHE["result"] is not None and (_now - _FULL_DIAG_CACHE["ts"]) < _FULL_DIAG_TTL_SEC:
        cached = _FULL_DIAG_CACHE["result"]
        return dict(cached, from_cache=True)
    # rev33: 并发跑 4 个本地 check (gpu + pytorch + stock providers + python packages)
    # 总耗时从 ~30s 降到 ~max(check_python_packages=17s)
    with ThreadPoolExecutor(max_workers=4) as _ex:
        _f_gpu = _ex.submit(check_gpu)
        _f_pt = _ex.submit(check_pytorch)
        _f_stock = _ex.submit(check_stock_providers)
        _f_pkgs = _ex.submit(check_python_packages)
        gpu = _f_gpu.result(timeout=30)
        pytorch = _f_pt.result(timeout=30)
        stock_external = _f_stock.result(timeout=30)
        python_packages = _f_pkgs.result(timeout=30)
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
    # rev33: P7-1..P7-4 MiniMax 全模态 provider 健康度 (TTS/Music/Image/Video) 并发 probe,
    # 注意: 只在有 MINIMAX_API_KEY 时才查, 避免无 key 时 401 噪音. 4 个 probe 并发,
    # 总耗时从 ~108s 串行降到 ~max(单 probe timeout). 失败用 try/except 包成错误 dict.
    # stock_external 已在上面 concurrent 段跑过, 此处不再重复
    # 合并 stock_external (concurrent 已跑) 进 external, 然后并发加 minimax probes
    external = stock_external
    api_key = os.getenv("MINIMAX_API_KEY")
    base_url = "https://api.minimaxi.com"
    if api_key:
        def _probe(fn_name):
            try:
                return fn_name.replace("check_minimax_", ""), globals()[fn_name](api_key=api_key, base_url=base_url)
            except Exception as exc:
                short = fn_name.replace("check_minimax_", "")
                return short, {"provider": short, "ok": False, "error": str(exc)}
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = [ex.submit(_probe, n) for n in ("check_minimax_tts", "check_minimax_music", "check_minimax_image", "check_minimax_video")]
            for fut in futures:
                try:
                    name, payload = fut.result(timeout=70)
                except Exception as exc:
                    name, payload = "minimax_unknown", {"provider": "minimax_unknown", "ok": False, "error": str(exc)}
                external[name] = payload
        # minimax_video 保留 skipped 标记 (视频生成额度限制, 仅 healthcheck 不实际生成)
        if external.get("minimax_video", {}).get("ok") is True:
            external["minimax_video"]["skipped"] = True
            external["minimax_video"]["reason"] = "视频生成额度受限，环境检查禁止自动提交生成任务"
        elif "minimax_video" not in external:
            external["minimax_video"] = {
                "provider": "minimax_video",
                "ok": None,
                "skipped": True,
                "error": None,
                "reason": "视频生成额度受限，环境检查禁止自动提交生成任务",
            }
    capability_groups = build_capability_groups(provider_configs, ffmpeg_available=check_ffmpeg().get("available", False), gpt_sovits_info=gpt_info, wav2lip_info=wav_info, capabilities=check_render_capability(gpu, pytorch))
    # external 已在 minimax 段合并 stock_external, 不再重复赋值
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "python": check_python(), "node": check_node(), "ffmpeg": check_ffmpeg(), "ffprobe": check_ffprobe(), "cpu": check_cpu(), "memory": check_memory(), "disk": check_disk(), "gpu": gpu, "pytorch": pytorch, "python_packages": python_packages, "workspace": check_workspace(), "gpt_sovits": gpt_info, "wav2lip_onnx": wav_info, "external_providers": external, "capabilities": check_render_capability(gpu, pytorch), "capability_groups": capability_groups}
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
    # rev33: 写缓存供下次刷新秒回 (30s TTL)
    _FULL_DIAG_CACHE["result"] = report
    _FULL_DIAG_CACHE["ts"] = time.time()
    return dict(report, from_cache=False)

if __name__ == "__main__":
    print(json.dumps(run_full_diagnostic(), ensure_ascii=False, indent=2))


def check_minimax_tts(api_key=None, base_url=None, timeout=8.0):
    """P7-1 MiniMax TTS cloud healthcheck.
    Returns {base_url, ok, latency_ms, http_status, error, model}."""
    started = time.time()
    api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
    base_url = base_url or os.getenv("FLIKI_MINIMAX_BASE_URL", "https://api.minimaxi.com")
    model = os.getenv("FLIKI_MINIMAX_MODEL", "speech-02-turbo")
    if not api_key:
        return {"base_url": base_url, "ok": False, "latency_ms": 0,
                "http_status": None, "error": "MINIMAX_API_KEY not set", "model": model}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{base_url}/v1/t2a_v2",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "text": "hi",
                    "stream": False,
                    "voice_setting": {"voice_id": "male-qn-qingse", "speed": 1.0, "vol": 1.0, "pitch": 0},
                    "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
                },
            )
        latency_ms = int((time.time() - started) * 1000)
        if r.status_code == 401:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": 401, "error": "invalid API key", "model": model}
        if r.status_code >= 500:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": f"server HTTP {r.status_code}", "model": model}
        if r.status_code >= 400:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": r.text[:200], "model": model}
        try:
            body = r.json()
            ok = body.get("base_resp", {}).get("status_code") == 0
            err = None if ok else body.get("base_resp", {}).get("status_msg", "unknown")
        except Exception:
            ok = False
            err = "invalid JSON"
        return {"base_url": base_url, "ok": ok, "latency_ms": latency_ms,
                "http_status": r.status_code, "error": err, "model": model}
    except httpx.HTTPError as exc:
        return {"base_url": base_url, "ok": False,
                "latency_ms": int((time.time() - started) * 1000),
                "http_status": None, "error": str(exc), "model": model}


def check_minimax_music(api_key=None, base_url=None, timeout=60.0):
    """P7-2 MiniMax Music cloud healthcheck (music-3.0).
    Returns {base_url, ok, latency_ms, http_status, error, model}."""
    started = time.time()
    api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
    base_url = base_url or os.getenv("FLIKI_MINIMAX_BASE_URL", "https://api.minimaxi.com")
    model = os.getenv("FLIKI_MINIMAX_MUSIC_MODEL", "music-3.0")
    if not api_key:
        return {"base_url": base_url, "ok": False, "latency_ms": 0,
                "http_status": None, "error": "MINIMAX_API_KEY not set", "model": model}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{base_url}/v1/music_generation",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "prompt": "calm piano, 5 second loop",
                    "lyrics": "[instrumental]",
                    "audio_setting": {"sample_rate": 44100, "bitrate": 256000, "format": "mp3"},
                },
            )
        latency_ms = int((time.time() - started) * 1000)
        if r.status_code == 401:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": 401, "error": "invalid API key", "model": model}
        if r.status_code >= 500:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": f"server HTTP {r.status_code}", "model": model}
        if r.status_code >= 400:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": r.text[:200], "model": model}
        try:
            body = r.json()
            ok = body.get("base_resp", {}).get("status_code") == 0
            err = None if ok else body.get("base_resp", {}).get("status_msg", "unknown")
        except Exception:
            ok = False
            err = "invalid JSON"
        return {"base_url": base_url, "ok": ok, "latency_ms": latency_ms,
                "http_status": r.status_code, "error": err, "model": model}
    except httpx.HTTPError as exc:
        return {"base_url": base_url, "ok": False,
                "latency_ms": int((time.time() - started) * 1000),
                "http_status": None, "error": str(exc), "model": model}


def check_minimax_image(api_key=None, base_url=None, timeout=30.0):
    """P7-3 MiniMax Image cloud healthcheck (image-01).
    Returns {base_url, ok, latency_ms, http_status, error, model}."""
    started = time.time()
    api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
    base_url = base_url or os.getenv("FLIKI_MINIMAX_BASE_URL", "https://api.minimaxi.com")
    model = os.getenv("FLIKI_MINIMAX_IMAGE_MODEL", "image-01")
    if not api_key:
        return {"base_url": base_url, "ok": False, "latency_ms": 0,
                "http_status": None, "error": "MINIMAX_API_KEY not set", "model": model}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{base_url}/v1/image_generation",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "prompt": "blue sky",
                    "aspect_ratio": "1:1",
                    "response_format": "url",
                    "n": 1,
                    "prompt_optimizer": False,
                },
            )
        latency_ms = int((time.time() - started) * 1000)
        if r.status_code == 401:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": 401, "error": "invalid API key", "model": model}
        if r.status_code >= 500:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": f"server HTTP {r.status_code}", "model": model}
        if r.status_code >= 400:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": r.text[:200], "model": model}
        try:
            body = r.json()
            ok = body.get("base_resp", {}).get("status_code") == 0
            err = None if ok else body.get("base_resp", {}).get("status_msg", "unknown")
        except Exception:
            ok = False
            err = "invalid JSON"
        return {"base_url": base_url, "ok": ok, "latency_ms": latency_ms,
                "http_status": r.status_code, "error": err, "model": model}
    except httpx.HTTPError as exc:
        return {"base_url": base_url, "ok": False,
                "latency_ms": int((time.time() - started) * 1000),
                "http_status": None, "error": str(exc), "model": model}


def check_minimax_video(api_key=None, base_url=None, timeout=10.0):
    """P7-4 MiniMax Video cloud healthcheck (Hailuo-2.3).
    Only verifies submit endpoint accepts the key; does not actually
    generate a 6s 1080P video (would cost credits + several minutes).
    Returns {base_url, ok, latency_ms, http_status, error, model}."""
    started = time.time()
    api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
    base_url = base_url or os.getenv("FLIKI_MINIMAX_BASE_URL", "https://api.minimaxi.com")
    model = os.getenv("FLIKI_MINIMAX_VIDEO_MODEL", "MiniMax-Hailuo-2.3")
    if not api_key:
        return {"base_url": base_url, "ok": False, "latency_ms": 0,
                "http_status": None, "error": "MINIMAX_API_KEY not set", "model": model}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(
                f"{base_url}/v1/video_generation",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "prompt": "blue sky",
                    "duration": 6,
                    "resolution": "768P",
                },
            )
        latency_ms = int((time.time() - started) * 1000)
        if r.status_code == 401:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": 401, "error": "invalid API key", "model": model}
        if r.status_code >= 500:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": f"server HTTP {r.status_code}", "model": model}
        if r.status_code >= 400:
            return {"base_url": base_url, "ok": False, "latency_ms": latency_ms,
                    "http_status": r.status_code, "error": r.text[:200], "model": model}
        try:
            body = r.json()
            ok = body.get("base_resp", {}).get("status_code") == 0
            err = None if ok else body.get("base_resp", {}).get("status_msg", "unknown")
        except Exception:
            ok = False
            err = "invalid JSON"
        return {"base_url": base_url, "ok": ok, "latency_ms": latency_ms,
                "http_status": r.status_code, "error": err, "model": model}
    except httpx.HTTPError as exc:
        return {"base_url": base_url, "ok": False,
                "latency_ms": int((time.time() - started) * 1000),
                "http_status": None, "error": str(exc), "model": model}
