from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], timeout: int) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "unknown ffmpeg error").strip()
        raise RuntimeError(message[-1000:])


def probe_duration(path: str | Path, ffprobe_binary: str = "ffprobe") -> float:
    completed = subprocess.run(
        [ffprobe_binary, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=20,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    value = (completed.stdout or "").strip()
    if completed.returncode != 0 or not value:
        raise RuntimeError(f"Cannot probe avatar audio duration: {(completed.stderr or '').strip()[-500:]}")
    return float(value)


def build_segments(duration: float, minimum_seconds: float = 2.0, maximum_seconds: float = 6.0) -> list[tuple[float, float]]:
    if duration <= 0:
        raise ValueError("duration must be positive")
    minimum_seconds = max(0.5, float(minimum_seconds))
    maximum_seconds = max(minimum_seconds, float(maximum_seconds))
    if duration <= maximum_seconds:
        return [(0.0, duration)]
    count = max(2, int((duration + maximum_seconds - 1e-9) // maximum_seconds))
    while count > 1 and duration / count < minimum_seconds:
        count -= 1
    segment_duration = duration / count
    segments = []
    start = 0.0
    for index in range(count):
        end = duration if index == count - 1 else min(duration, start + segment_duration)
        segment_start = round(start, 6)
        segment_length = round(end - start, 6)
        if index == count - 1:
            segment_length = round(duration - sum(item[1] for item in segments), 6)
        segments.append((segment_start, segment_length))
        start = end
    return segments


def _cache_key(face: Path, audio: Path, model: Path | None, segments: list[tuple[float, float]], fps: float, max_dimension: int) -> str:
    payload = {
        "face": _sha256_file(face),
        "audio": _sha256_file(audio),
        "model": _sha256_file(model) if model and model.is_file() else None,
        "segments": segments,
        "fps": fps,
        "max_dimension": max_dimension,
        "version": 1,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def synthesize_segmented_avatar(
    face_path: str | Path,
    audio_path: str | Path,
    destination_path: str | Path,
    provider_factory: Callable[[], Any],
    *,
    cache_dir: str | Path,
    model_path: str | Path | None = None,
    minimum_seconds: float = 2.0,
    maximum_seconds: float = 6.0,
    fps: float = 25.0,
    max_dimension: int = 320,
    ffmpeg_binary: str = "ffmpeg",
    ffprobe_binary: str = "ffprobe",
) -> dict[str, Any]:
    face = Path(face_path).resolve()
    audio = Path(audio_path).resolve()
    destination = Path(destination_path).resolve()
    model = Path(model_path).resolve() if model_path else None
    if not face.is_file() or not audio.is_file():
        raise FileNotFoundError("Avatar face or audio is missing")
    duration = probe_duration(audio, ffprobe_binary)
    segments = build_segments(duration, minimum_seconds, maximum_seconds)
    cache_root = Path(cache_dir).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    key = _cache_key(face, audio, model, segments, fps, max_dimension)
    cached_video = cache_root / f"{key}.mp4"
    cached_meta = cache_root / f"{key}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if cached_video.is_file() and cached_video.stat().st_size > 1024:
        shutil.copy2(cached_video, destination)
        metadata = json.loads(cached_meta.read_text(encoding="utf-8")) if cached_meta.is_file() else {}
        metadata.update({"local_path": str(destination), "cache_hit": True, "cache_key": key})
        return metadata

    provider = provider_factory()
    segment_results = []
    with tempfile.TemporaryDirectory(prefix="avatar-segments-", dir=str(destination.parent)) as temporary:
        work_dir = Path(temporary)
        video_parts = []
        for index, (start, length) in enumerate(segments):
            audio_part = work_dir / f"audio-{index:03d}.wav"
            video_part = work_dir / f"video-{index:03d}.mp4"
            _run([
                ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-ss", f"{start:.6f}", "-t", f"{length:.6f}",
                "-i", str(audio), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-y", str(audio_part),
            ], timeout=60)
            result = provider.synthesize(face, audio_part, video_part)
            if not video_part.is_file() or video_part.stat().st_size <= 1024:
                raise RuntimeError(f"Wav2Lip segment {index} did not produce a valid MP4")
            video_parts.append(video_part)
            segment_results.append({
                "index": index, "start_seconds": start, "duration_seconds": length,
                "mode": result.get("mode"), "fallback_used": bool(result.get("fallback_used")),
                "elapsed_seconds": result.get("elapsed_seconds"),
            })
        concat_file = work_dir / "concat.txt"
        concat_file.write_text("".join(f"file '{part.as_posix()}'\n" for part in video_parts), encoding="utf-8")
        silent_joined = work_dir / "joined.mp4"
        _run([ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", "-y", str(silent_joined)], timeout=120)
        _run([
            ffmpeg_binary, "-hide_banner", "-loglevel", "error", "-i", str(silent_joined), "-i", str(audio),
            "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", "-y", str(destination),
        ], timeout=120)

    fallback_used = any(item["fallback_used"] for item in segment_results)
    metadata = {
        "provider": "wav2lip_onnx_segmented",
        "mode": "segmented_wav2lip_onnx" if not fallback_used else "segmented_static_fallback",
        "fallback_used": fallback_used,
        "model_present": bool(model and model.is_file()),
        "local_path": str(destination),
        "duration_seconds": duration,
        "segment_count": len(segment_results),
        "segments": segment_results,
        "cache_hit": False,
        "cache_key": key,
    }
    shutil.copy2(destination, cached_video)
    cached_meta.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata
