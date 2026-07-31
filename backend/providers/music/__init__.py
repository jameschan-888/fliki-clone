import os
import shutil
import subprocess
from pathlib import Path

import httpx

from providers.base import ProviderError, MusicProvider


# P7-Fallback: 5 秒静音 MP3 兜底字节.
# 写在 ffmpeg 不可用时; 项目其他流程 (ffmpeg concat, Remotion 渲染) 能容忍静默音频.
# 内容: ID3v2.3 header + 4 字节 "FLIK" tag.
_SILENCE_PLACEHOLDER_MP3 = (
    b"ID3\x03\x00\x00\x00\x00\x00\x00"  # ID3v2.3 header
    b"FLIK"  # custom tag, 表明这是兜底占位
)


class FreesoundProvider(MusicProvider):
    name = "freesound"
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("FREESOUND_API_KEY", "")

    def fetch(self, query, destination):
        if not self.api_key:
            raise ProviderError("FREESOUND_API_KEY is missing")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        params = {
            "query": query,
            "token": self.api_key,
            "fields": "id,name,username,license,previews,url,duration",
            "page_size": 10,
            "filter": "duration:[20 TO 300]",
        }
        with httpx.Client(timeout=30) as client:
            response = client.get(
                "https://freesound.org/apiv2/search/text/", params=params
            )
            response.raise_for_status()
            results = response.json().get("results", [])
            if not results:
                raise ProviderError(f"Freesound returned no audio for {query}")
            selected = results[0]
            url = (selected.get("previews", {}) or {}).get("preview-hq-mp3") or (
                selected.get("previews", {}) or {}
            ).get("preview-lq-mp3")
            if not url:
                raise ProviderError("Freesound result has no MP3 preview")
            with client.stream("GET", url, follow_redirects=True) as stream:
                stream.raise_for_status()
                with destination.open("wb") as output:
                    for chunk in stream.iter_bytes():
                        output.write(chunk)
        return {
            "provider": self.name,
            "source_url": url,
            "page_url": selected.get("url"),
            "creator": selected.get("username"),
            "license": selected.get("license"),
            "duration_seconds": selected.get("duration"),
            "local_path": str(destination),
        }


class SilenceMusicProvider(MusicProvider):
    """P7-Fallback: 永远成功的兜底, 生成 5 秒静音 MP3.

    设计: 用 ffmpeg lavfi 生成静音; ffmpeg 不在 PATH 时退化到最小占位字节.
    Pipeline 调用 fetch_music_with_fallback 时, 任何上游失败都会到这里,
    永远不会因为"音乐拿不到"而整个 workflow 跑挂.
    """

    name = "silence"
    DEFAULT_DURATION_SEC = 5.0

    def fetch(self, query, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin:
            try:
                subprocess.run(
                    [
                        ffmpeg_bin,
                        "-y",
                        "-f",
                        "lavfi",
                        "-i",
                        "anullsrc=r=44100:cl=mono",
                        "-t",
                        str(self.DEFAULT_DURATION_SEC),
                        "-q:a",
                        "9",
                        "-acodec",
                        "libmp3lame",
                        str(destination),
                    ],
                    capture_output=True,
                    check=True,
                    timeout=10,
                )
                return {
                    "provider": self.name,
                    "source_url": None,
                    "local_path": str(destination),
                    "duration_seconds": self.DEFAULT_DURATION_SEC,
                    "is_silence_fallback": True,
                }
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                OSError,
            ):
                # ffmpeg 失败: 退化到占位字节.
                pass
        # 退化: 写最小占位 MP3. 后续 concat 可能需要替换.
        destination.write_bytes(_SILENCE_PLACEHOLDER_MP3)
        return {
            "provider": self.name,
            "source_url": None,
            "local_path": str(destination),
            "duration_seconds": self.DEFAULT_DURATION_SEC,
            "is_silence_fallback": True,
            "is_placeholder": True,
        }


# ===== P7-2 MiniMax Music HTTP adapter (cloud API, music-3.0) =====
from .minimax_music import MiniMaxMusicProvider, MiniMaxMusicError  # noqa: F401


def build_minimax_music_provider(api_key=None, model="music-3.0", timeout=60.0):
    return MiniMaxMusicProvider(api_key=api_key, model=model, timeout=timeout)


# ===== P7-Fallback music chain =====
def fetch_music_with_fallback(query, destination, *, prefer: str | None = None):
    """P7-Fallback: 音乐三级兜底链, 永不抛错.

    顺序: freesound (有 key) -> minimax_music (有 key) -> silence
    prefer="freesound"|"minimax_music"|"silence" 可把指定 provider 提到第一位.
    返回的 dict 必带 "provider" 字段, 调用方据此判断走了哪条链.
    """
    from providers.base import ProviderError as _PE  # local alias 避免遮蔽
    errors: list[str] = []

    candidates = []
    if prefer == "freesound":
        candidates.append(("freesound", lambda: FreesoundProvider().fetch(query, destination)))
    if prefer == "minimax_music" and os.getenv("MINIMAX_API_KEY"):
        candidates.append(("minimax_music", lambda: build_minimax_music_provider().fetch(query, destination)))

    if not any(name == "freesound" for name, _ in candidates) and os.getenv("FREESOUND_API_KEY"):
        candidates.append(("freesound", lambda: FreesoundProvider().fetch(query, destination)))
    if not any(name == "minimax_music" for name, _ in candidates) and os.getenv("MINIMAX_API_KEY"):
        candidates.append(("minimax_music", lambda: build_minimax_music_provider().fetch(query, destination)))
    if prefer == "silence":
        candidates.append(("silence", lambda: SilenceMusicProvider().fetch(query, destination)))
    if not any(name == "silence" for name, _ in candidates):
        candidates.append(("silence", lambda: SilenceMusicProvider().fetch(query, destination)))

    for name, fn in candidates:
        try:
            return fn()
        except _PE as exc:
            errors.append(f"{name}: {exc}")
        except Exception as exc:  # noqa: BLE001 - 兜底链要吞掉所有非 ProviderError
            errors.append(f"{name}: {exc}")
    # 不会到这里 (silence 兜底永远成功), 留个保险.
    raise _PE("music fallback chain exhausted: " + "; ".join(errors))
