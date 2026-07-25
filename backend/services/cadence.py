"""配音卡点：ffmpeg silencedetect → 语音段起点。

借鉴灵剪 capabilities/cadence/cadence.py。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


class CadenceError(RuntimeError):
    pass


def detect_voice_segments(
    audio_path: str | Path,
    noise_db: str = "-30dB",
    min_duration: float = 0.4,
    ffmpeg_binary: str | None = None,
) -> list[dict[str, float | int]]:
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        raise CadenceError(f"音频不存在: {audio_path}")
    ffmpeg = ffmpeg_binary or shutil.which("ffmpeg")
    if not ffmpeg:
        raise CadenceError("ffmpeg 不在 PATH，无法做 cadence")
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(audio_path),
        "-af",
        f"silencedetect=noise={noise_db}:d={min_duration}",
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=120)
    stderr = (proc.stderr or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0 and "silence_end" not in stderr:
        raise CadenceError(f"ffmpeg silencedetect 失败 (rc={proc.returncode}): {stderr[-300:]}")
    pattern = re.compile(r"silence_end: ([0-9.]+)\s*\|\s*silence_duration: ([0-9.]+)")
    segments: list[dict[str, float | int]] = [{"start": 0.0, "silence_after": 0.0}]
    for match in pattern.finditer(stderr):
        end = round(float(match.group(1)), 3)
        dur = round(float(match.group(2)), 3)
        segments.append({"start": end, "silence_after": dur})
    return segments


def suggest_scene_end(start: float, min_tail: float = 0.5) -> float:
    return round(start + min_tail, 3)


def cadence_summary(segments: list[dict[str, float | int]]) -> dict[str, float | int]:
    if not segments:
        return {"count": 0, "avg_silence": 0.0, "max_silence": 0.0}
    silences = [float(seg.get("silence_after", 0.0)) for seg in segments] or [0.0]
    return {
        "count": len(segments),
        "avg_silence": round(sum(silences) / len(silences), 3),
        "max_silence": round(max(silences), 3),
    }
