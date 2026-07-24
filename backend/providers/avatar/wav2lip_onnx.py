# P5E thin wrapper around wav2lip_prototype.Wav2LipProvider.
# Exposes a single AvatarProvider ABC-shaped entry point so the rest of the
# codebase never imports the prototype directly. All inference + download +
# fallback behaviour stays inside the prototype.
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from providers.base import ProviderError
from wav2lip_prototype import Wav2LipProvider


AVATAR_CLONE_PREFIX = "avatar:"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "wav2lip_onnx"


class Wav2LipONNXAvatarProvider:
    """CPU-friendly talking-head provider (P5E).

    Required AvatarProvider-shaped methods:
      - name (str): "wav2lip_onnx"
      - synthesize(face_image, audio, destination, ...) -> dict

    The underlying wav2lip_prototype.Wav2LipProvider is responsible for
    downloading the ONNX model when auto_download=True (off by default),
    running inference via onnxruntime, and falling back to a static-image
    FFmpeg composite when the model is missing or fails.
    """

    name = "wav2lip_onnx"

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        auto_download: bool | None = None,
        ffmpeg_binary: str = "ffmpeg",
        max_dimension: int = 320,
        fps: float = 25.0,
    ):
        resolved_model = (
            Path(model_path).expanduser()
            if model_path
            else Path(os.getenv("FLIKI_WAV2LIP_MODEL", str(DEFAULT_MODEL_DIR / "wav2lip.onnx")))
        )
        resolved_model.parent.mkdir(parents=True, exist_ok=True)
        if auto_download is None:
            auto_download = os.getenv("FLIKI_WAV2LIP_AUTO_DOWNLOAD", "0").lower() in {"1", "true", "yes"}
        self._impl = Wav2LipProvider(
            model_path=resolved_model,
            auto_download=auto_download,
            ffmpeg_binary=ffmpeg_binary,
            fps=fps,
        )
        self._max_dimension = int(max_dimension)

    # ------------------------------------------------------------------
    # AvatarProvider-shaped public API
    # ------------------------------------------------------------------
    def synthesize(
        self,
        face_image_path: str | Path,
        audio_path: str | Path,
        destination_path: str | Path,
    ) -> dict[str, Any]:
        if not Path(face_image_path).is_file():
            raise ProviderError(f"Avatar face image not found: {face_image_path!r}")
        if not Path(audio_path).is_file():
            raise ProviderError(f"Avatar audio not found: {audio_path!r}")
        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = self._impl.synthesize(face_image_path, audio_path, destination)
        if result.get("status") != "success":
            # Always produce an MP4 (the prototype already falls back to FFmpeg),
            # but surface upstream errors here for callers who care.
            raise ProviderError(
                f"Wav2Lip synthesis failed (mode={result.get('mode')}): {result.get('reason') or 'unknown'}"
            )
        return {
            "provider": self.name,
            "mode": result.get("mode"),
            "fallback_used": result.get("fallback_used", False),
            "model_present": result.get("model_present", False),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "local_path": result.get("output_path"),
        }

    def healthcheck(self) -> dict[str, Any]:
        started = time.time()
        info: dict[str, Any] = {
            "provider": self.name,
            "model_path": str(self._impl.model_path),
            "model_present": self._impl.model_path.is_file(),
            "auto_download": bool(self._impl.auto_download),
            "ffmpeg_available": False,
            "dependencies_ok": False,
            "dependency_warnings": [],
        }
        for mod_name in ("cv2", "librosa", "onnxruntime", "numpy"):
            try:
                __import__(mod_name)
            except Exception as exc:  # pragma: no cover - system check
                info["dependency_warnings"].append(f"{mod_name}: {type(exc).__name__}")
        info["dependencies_ok"] = not info["dependency_warnings"]
        try:
            import shutil
            info["ffmpeg_available"] = bool(shutil.which(self._impl.ffmpeg_binary))
        except Exception:
            pass
        info["latency_ms"] = int((time.time() - started) * 1000)
        info["ok"] = info["ffmpeg_available"] and info["dependencies_ok"]
        info["error"] = None if info["ok"] else "Missing python deps or ffmpeg; will fall back to static_avatar"
        return info


def build_wav2lip_provider(
    *,
    model_path: str | None = None,
    auto_download: bool | None = None,
    ffmpeg_binary: str = "ffmpeg",
    max_dimension: int = 320,
    fps: float = 25.0,
) -> Wav2LipONNXAvatarProvider:
    return Wav2LipONNXAvatarProvider(
        model_path=model_path,
        auto_download=auto_download,
        ffmpeg_binary=ffmpeg_binary,
        max_dimension=max_dimension,
        fps=fps,
    )


def detect_provider_for_voice_clone(voice: str | None) -> str | None:
    """Return 'wav2lip_onnx' when a scene voice references a clone uuid.

    Kept here so future avatar providers (Sadtalker, MuseTalk) can plug in.
    """
    if not voice:
        return None
    return None
