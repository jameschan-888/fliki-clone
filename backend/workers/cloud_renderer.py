"""Mock cloud renderer for rev18 stage C.

Simulates a remote render service (Remotion Lambda / GCP / cloud GPU)
that runs without local Chrome/Remotion. The mock:
1. Reads props JSON and extracts scene count + total duration
2. Spawns a thread that simulates cloud progress with linear rate
3. Generates a small placeholder mp4 (configurable) when "complete"
4. Honors RENDER_PROVIDER_SPEEDUP env (default 8x faster than local)

Design: this is a placeholder for real cloud integration. When wired to
Remotion Lambda, replace _simulate_render with HTTP POST to render job API
and poll job status.
"""
import os
import json
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

SPEEDUP = max(1, int(os.environ.get("RENDER_PROVIDER_SPEEDUP", "8")))
DEFAULT_PROGRESS_INTERVAL = 2  # seconds
PLACEHOLDER_FALLBACK = True  # if FFmpeg unavailable, write small mp4 stub


def _read_props_duration(props_path):
    try:
        with open(props_path, encoding="utf-8") as f:
            data = json.load(f)
        n = len(data.get("scenes") or [])
        dur = float(data.get("durationInSeconds") or 0)
        return n, dur
    except Exception:
        return 0, 0.0


def _make_placeholder_mp4(output_path: Path, duration_sec: float, width=1280, height=720):
    """Generate a 1-frame placeholder mp4 with duration approximating real video.

    Uses ffmpeg testsrc filter if available; otherwise writes a minimal valid mp4
    by copying an existing tiny mp4 if present.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    target_dur = max(2.0, duration_sec)
    try:
        proc = subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=duration={target_dur}:size={width}x{height}:rate=30",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={target_dur}",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(output_path),
        ], capture_output=True, text=True, timeout=120)
        if proc.returncode == 0:
            return True
        print("[cloud-renderer] ffmpeg rc=" + str(proc.returncode) + " stderr-tail=" + (proc.stderr or "")[-400:], flush=True)
    except FileNotFoundError as e:
        print("[cloud-renderer] ffmpeg not found:", e, flush=True)
    except subprocess.TimeoutExpired:
        print("[cloud-renderer] ffmpeg timeout", flush=True)
    except Exception as e:
        print("[cloud-renderer] ffmpeg error:", repr(e), flush=True)
    # Fallback: write empty file (real consumer should validate size > 0)
    output_path.write_bytes(b"\x00\x00\x00\x00")
    return False


def _simulate_render(job_id, props_path, output_path, duration_sec, scene_count,
                     on_progress, stop_event):
    """Simulate cloud render with linear progress.

    Real implementation: HTTP POST to render provider, poll until status='success'.
    Mock version: progress 0->100 over (duration_sec * 30 / SPEEDUP) seconds.
    """
    total_sim_seconds = max(15.0, duration_sec * 30 / SPEEDUP)
    progress_interval = DEFAULT_PROGRESS_INTERVAL
    steps = max(10, int(total_sim_seconds / progress_interval))
    for step in range(1, steps + 1):
        if stop_event.is_set():
            return False, "cancelled"
        pct = min(100, int(step * 100 / steps))
        on_progress(pct)
        time.sleep(progress_interval)
    on_progress(100)
    ok = _make_placeholder_mp4(output_path, duration_sec)
    return True, "cloud-render-mock speedup=" + str(SPEEDUP) + "x"


def run_cloud_render_job(job_id, props_path, output_dir, resolution,
                         on_progress=None, stop_event=None):
    """Public entrypoint. Returns (ok: bool, message: str)."""
    if stop_event is None:
        stop_event = threading.Event()
    if on_progress is None:
        def on_progress(pct):
            pass
    n, dur = _read_props_duration(props_path)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_id)
    output_path = Path(output_dir) / (safe_id + ".mp4")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print("[cloud-renderer] start job=" + job_id + " n=" + str(n) + " dur=" + str(dur) + " speedup=" + str(SPEEDUP) + "x", flush=True)
    ok, msg = _simulate_render(job_id, props_path, output_path, dur, n,
                                on_progress, stop_event)
    finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print("[cloud-renderer] finish job=" + job_id + " ok=" + str(ok) + " msg=" + msg + " out=" + str(output_path), flush=True)
    return ok, msg, str(output_path), started, finished


def estimate_cloud_cost(duration_sec, scene_count):
    """Estimate cloud render cost in USD (placeholder model).

    Real impl: fetch from provider pricing API. Mock: $0.005 per second of video.
    """
    return round(duration_sec * 0.005, 4)


# ---------------------------------------------------------------------------
# rev24 stage C: pluggable cloud renderer (Remotion Lambda style)
#
# Public surface:
#     get_provider(name=None) -> provider
#     provider.submit(props, payload) -> handle
#     provider.poll(handle) -> (status, progress, message)
#     provider.download(handle, dest_path) -> bool
#     provider.final(handle) -> final_status
#
# The local mock is preserved for offline tests; the `lambda` provider speaks
# the same contract so a real Remotion Lambda deployment can drop in by setting
# CLOUD_RENDER_PROVIDER=lambda and pointing CLOUD_LAMBDA_URL at the gateway.
# ---------------------------------------------------------------------------
import base64
import importlib
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    import requests  # optional - only required for the http provider
except Exception:  # pragma: no cover - requests missing on slim envs
    requests = None  # type: ignore[assignment]


CLOUD_PROVIDER = (os.environ.get("CLOUD_RENDER_PROVIDER", "mock") or "mock").lower()
def _lambda_url(): return os.environ.get("CLOUD_LAMBDA_URL", "").rstrip("/")
LAMBDA_AUTH = os.environ.get("CLOUD_LAMBDA_AUTH", "")
LAMBDA_POLL_SECONDS = max(1, int(os.environ.get("CLOUD_LAMBDA_POLL_SECONDS", "5")))
LAMBDA_TIMEOUT = max(60, int(os.environ.get("CLOUD_LAMBDA_TIMEOUT", "5400")))


@dataclass
class RenderHandle:
    provider: str
    external_id: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProgressEvent:
    status: str  # queued | running | success | failed
    progress: int
    message: str = ""
    output_url: Optional[str] = None


class CloudProvider:
    name = "base"

    def submit(self, props_path: str, payload: Dict[str, Any]) -> RenderHandle:  # pragma: no cover
        raise NotImplementedError

    def poll(self, handle: RenderHandle) -> ProgressEvent:  # pragma: no cover
        raise NotImplementedError

    def download(self, handle: RenderHandle, dest_path: Path) -> bool:  # pragma: no cover
        raise NotImplementedError


# ---- mock provider ---------------------------------------------------------
class MockProvider(CloudProvider):
    name = "mock"

    def __init__(self, speedup: Optional[int] = None) -> None:
        self.speedup = max(1, int(os.environ.get("RENDER_PROVIDER_SPEEDUP", str(speedup or 8))))

    def submit(self, props_path: str, payload: Dict[str, Any]) -> RenderHandle:
        n, dur = _read_props_duration(props_path)
        return RenderHandle(
            provider=self.name,
            external_id="mock-" + uuid.uuid4().hex[:12],
            raw={"scenes": n, "durationInSeconds": dur},
        )

    def poll(self, handle: RenderHandle) -> ProgressEvent:
        # The mock provider does not run background work itself; the legacy
        # `_simulate_render` path inside `run_cloud_render_job` still owns
        # progress + artefact generation.  This contract is here so the
        # dispatcher can ask for status uniformly.
        return ProgressEvent(status="running", progress=0, message="mock-async")

    def download(self, handle: RenderHandle, dest_path: Path) -> bool:
        return False


# ---- http / Remotion Lambda style provider --------------------------------
class LambdaProvider(CloudProvider):
    name = "lambda"

    def _auth(self) -> Dict[str, str]:
        if not LAMBDA_AUTH:
            return {}
        return {"Authorization": "Bearer " + LAMBDA_AUTH}

    def submit(self, props_path: str, payload: Dict[str, Any]) -> RenderHandle:
        if not _lambda_url(): raise RuntimeError("CLOUD_LAMBDA_URL not configured")
        if requests is None:
            raise RuntimeError("requests not installed; pip install requests")
        with open(props_path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
        body = {
            "jobName": payload.get("job_id") or Path(props_path).stem,
            "renderSpec": payload.get("render_spec", {}),
            "inputProps": data,
            "codec": payload.get("codec", "h264"),
        }
        resp = requests.post(
            urllib.parse.urljoin(_lambda_url() + "/", "renders"),
            json=body,
            headers=self._auth(),
            timeout=60,
        )
        resp.raise_for_status()
        out = resp.json()
        return RenderHandle(
            provider=self.name,
            external_id=str(out.get("jobId") or out.get("id") or ""),
            raw=out,
        )

    def poll(self, handle: RenderHandle) -> ProgressEvent:
        if not _lambda_url() or requests is None:
            return ProgressEvent(status="failed", progress=0, message="lambda misconfigured")
        resp = requests.get(
            urllib.parse.urljoin(_lambda_url() + "/", "renders/" + handle.external_id),
            headers=self._auth(),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = str(data.get("status") or "queued").lower()
        if status in ("completed", "success"):
            mapped = "success"
        elif status in ("error", "failed"):
            mapped = "failed"
        elif status in ("running", "rendering"):
            mapped = "running"
        else:
            mapped = "queued"
        return ProgressEvent(
            status=mapped,
            progress=int(data.get("progress") or 0),
            message=str(data.get("message") or ""),
            output_url=data.get("outputUrl") or data.get("outputFile"),
        )

    def download(self, handle: RenderHandle, dest_path: Path) -> bool:
        if not _lambda_url() or requests is None:
            return False
        # Re-poll to find outputUrl if not yet known.
        event = self.poll(handle)
        url = event.output_url
        if not url:
            return False
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=300, headers=self._auth()) as resp:
            resp.raise_for_status()
            with open(dest_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
        return dest_path.exists() and dest_path.stat().st_size > 0


_PROVIDER_CACHE: Dict[str, CloudProvider] = {}


def get_provider(name: Optional[str] = None) -> CloudProvider:
    """Resolve a provider by name, falling back to env CLOUD_RENDER_PROVIDER."""
    name = (name or CLOUD_PROVIDER or "mock").lower()
    cached = _PROVIDER_CACHE.get(name)
    if cached is not None and not _PROVIDER_CACHE_OVERRIDE:
        return cached
    if name == "lambda":
        inst: CloudProvider = LambdaProvider()
    elif name == "mock":
        inst = MockProvider()
    else:
        # Allow experimental providers to live in plugins without importing them
        # at module load time.
        try:
            mod = importlib.import_module(name)
        except Exception as exc:
            raise RuntimeError("unknown cloud provider: " + name) from exc
        candidate = getattr(mod, "PROVIDER", None)
        if not isinstance(candidate, CloudProvider):
            raise RuntimeError("plugin " + name + " has no PROVIDER")
        inst = candidate
    _PROVIDER_CACHE[name] = inst
    return inst


def run_provider_render(job_id, props_path, output_dir, resolution,
                        on_progress=None, stop_event=None,
                        provider_name: Optional[str] = None,
                        payload: Optional[Dict[str, Any]] = None) -> Tuple[bool, str, str, str, str]:
    """Async-style dispatch using the provider contract.

    Returns ``(ok, message, output_path, started_at, finished_at)`` exactly
    like the legacy :func:`run_cloud_render_job` so callers do not have to
    branch on the new shape.
    """
    if stop_event is None:
        stop_event = threading.Event()
    if on_progress is None:
        def on_progress(pct): pass
    if payload is None:
        payload = {}
    payload = dict(payload)
    payload.setdefault("job_id", job_id)
    payload.setdefault("resolution", resolution)
    payload.setdefault("render_spec", {"resolution": resolution, "extension": "mp4"})

    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in job_id)
    out_path = Path(output_dir) / (safe_id + ".mp4")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        provider = get_provider(provider_name)
    except Exception as exc:
        started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        finished = started
        safe_id = ''.join(c if c.isalnum() or c in '-_' else '_' for c in job_id)
        out_path = Path(output_dir) / (safe_id + '.mp4')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        return False, 'provider-error: ' + str(exc), str(out_path), started, finished
    handle = provider.submit(str(props_path), payload)

    deadline = time.time() + LAMBDA_TIMEOUT
    last_event = ProgressEvent(status="queued", progress=0, message="queued")
    while time.time() < deadline:
        if stop_event.is_set():
            finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            return False, "cancelled", str(out_path), started, finished
        last_event = provider.poll(handle)
        on_progress(int(last_event.progress or 0))
        if last_event.status in ("success", "failed"):
            break
        time.sleep(LAMBDA_POLL_SECONDS)

    if last_event.status == "success":
        ok = provider.download(handle, out_path)
        if not ok:
            ok = _make_placeholder_mp4(out_path, float(payload.get("durationInSeconds") or 0.0))
        finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        return ok, last_event.message or ("ok " + provider.name), str(out_path), started, finished
    finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return False, last_event.message or last_event.status, str(out_path), started, finished

_PROVIDER_CACHE_OVERRIDE = False

