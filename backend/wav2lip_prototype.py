"""CPU-first Wav2Lip ONNX prototype with a static-avatar fallback."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any


class Wav2LipProvider:
    """Generate a talking-head MP4 with ONNX Runtime when possible.

    Model downloading is deliberately opt-in. Set auto_download=True or
    FLIKI_WAV2LIP_AUTO_DOWNLOAD=1 to let synthesize fetch a model.
    Every inference/download error falls back to an FFmpeg still-image video.
    """

    name = "wav2lip_onnx"
    DEFAULT_FPS = 25.0
    MODEL_SOURCES = (
        {
            "name": "modelscope-facefusion-assets",
            "url": (
                "https://www.modelscope.cn/models/cjc1887415157/"
                "facefusion-assets/resolve/master/wav2lip_gan.onnx"
            ),
        },
        {
            "name": "huggingface-bluefoxcreation",
            "url": (
                "https://huggingface.co/bluefoxcreation/Wav2lip-Onnx/"
                "resolve/main/wav2lip.onnx"
            ),
        },
        {
            "name": "github-facefusion-release",
            "url": (
                "https://github.com/facefusion/facefusion-assets/releases/"
                "download/models/wav2lip_gan.onnx"
            ),
        },
    )

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        auto_download: bool | None = None,
        ffmpeg_binary: str = "ffmpeg",
        fps: float = DEFAULT_FPS,
        download_timeout_seconds: int = 120,
    ) -> None:
        backend_dir = Path(__file__).resolve().parent
        self.model_path = Path(model_path or backend_dir / "data" / "wav2lip" / "wav2lip.onnx")
        env_download = os.getenv("FLIKI_WAV2LIP_AUTO_DOWNLOAD", "").strip().lower()
        self.auto_download = auto_download if auto_download is not None else env_download in {"1", "true", "yes"}
        self.ffmpeg_binary = ffmpeg_binary
        self.fps = float(fps)
        self.download_timeout_seconds = int(download_timeout_seconds)

    def synthesize(
        self,
        face_image_path: str | Path,
        audio_path: str | Path,
        destination_path: str | Path,
    ) -> dict[str, Any]:
        """Create an MP4 and return structured execution metadata."""
        started_at = time.perf_counter()
        face_path = Path(face_image_path).expanduser().resolve()
        source_audio_path = Path(audio_path).expanduser().resolve()
        output_path = Path(destination_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        result: dict[str, Any] = {
            "provider": self.name,
            "status": "processing",
            "mode": None,
            "output_path": str(output_path),
            "model_path": str(self.model_path.resolve()),
            "model_present": self.model_path.is_file(),
            "download_attempted": False,
            "fallback_used": False,
            "reason": None,
        }

        missing_inputs = [str(path) for path in (face_path, source_audio_path) if not path.is_file()]
        if missing_inputs:
            result.update(
                status="failed",
                mode="none",
                reason=f"Input file not found: {', '.join(missing_inputs)}",
                elapsed_seconds=round(time.perf_counter() - started_at, 3),
            )
            return result

        inference_error: str | None = None
        if not self.model_path.is_file() and self.auto_download:
            result["download_attempted"] = True
            download_result = self.download_model()
            result["download"] = download_result
            if not download_result["ok"]:
                inference_error = download_result["error"]

        if self.model_path.is_file():
            try:
                self._synthesize_onnx(face_path, source_audio_path, output_path)
                result.update(
                    status="success",
                    mode="wav2lip_onnx",
                    model_present=True,
                    elapsed_seconds=round(time.perf_counter() - started_at, 3),
                )
                return result
            except Exception as exc:
                inference_error = f"ONNX inference unavailable: {type(exc).__name__}: {exc}"
        elif inference_error is None:
            inference_error = (
                "Wav2Lip ONNX model is absent and automatic download is disabled; "
                "set FLIKI_WAV2LIP_AUTO_DOWNLOAD=1 to enable it"
            )

        fallback_result = self._fallback_static(face_path, source_audio_path, output_path)
        result.update(
            status="success" if fallback_result["ok"] else "failed",
            mode="static_avatar" if fallback_result["ok"] else "none",
            fallback_used=True,
            reason=inference_error,
            fallback=fallback_result,
            model_present=self.model_path.is_file(),
            elapsed_seconds=round(time.perf_counter() - started_at, 3),
        )
        return result

    def download_model(self) -> dict[str, Any]:
        """Try configured mirrors in order and atomically install the model."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        errors: list[str] = []
        for source in self.MODEL_SOURCES:
            try:
                metadata = self._download_from_url(source["url"], self.model_path)
                return {"ok": True, "source": source["name"], **metadata}
            except Exception as exc:
                errors.append(f"{source['name']}: {type(exc).__name__}: {exc}")
        return {"ok": False, "source": None, "error": " | ".join(errors)}

    def _download_from_url(self, url: str, destination: Path) -> dict[str, Any]:
        temporary_path = destination.with_suffix(destination.suffix + ".download")
        temporary_path.unlink(missing_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Fliki-Wav2Lip-Prototype/1.0"})
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with urllib.request.urlopen(request, timeout=self.download_timeout_seconds) as response:
                with temporary_path.open("wb") as output_file:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output_file.write(chunk)
                        digest.update(chunk)
                        size_bytes += len(chunk)
            if size_bytes < 10 * 1024 * 1024:
                raise RuntimeError(f"downloaded file is too small ({size_bytes} bytes)")
            temporary_path.replace(destination)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise
        return {
            "url": url,
            "size_bytes": size_bytes,
            "sha256": digest.hexdigest(),
            "path": str(destination.resolve()),
        }

    def _synthesize_onnx(self, face_path: Path, audio_path: Path, output_path: Path) -> None:
        np, cv2, librosa, ort = self._load_inference_dependencies()
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = max(1, min(8, os.cpu_count() or 1))
        session = ort.InferenceSession(
            str(self.model_path),
            sess_options=session_options,
            providers=["CPUExecutionProvider"],
        )

        source_frame = cv2.imread(str(face_path), cv2.IMREAD_COLOR)
        if source_frame is None:
            raise ValueError(f"OpenCV cannot read face image: {face_path}")
        face_box = self._detect_face(cv2, source_frame)

        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="wav2lip-", dir=self.model_path.parent) as temp_dir:
            temp_path = Path(temp_dir)
            pcm_path = temp_path / "audio-16k.wav"
            silent_video_path = temp_path / "silent.avi"
            self._extract_pcm_audio(audio_path, pcm_path)
            mel = self._wav2lip_mel(np, librosa, pcm_path)
            mel_chunks = self._split_mel(np, mel)
            self._render_frames(
                np=np,
                cv2=cv2,
                session=session,
                source_frame=source_frame,
                face_box=face_box,
                mel_chunks=mel_chunks,
                destination=silent_video_path,
            )
            self._mux_audio(silent_video_path, audio_path, output_path)

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("ONNX pipeline did not create a non-empty MP4")

    @staticmethod
    def _load_inference_dependencies() -> tuple[Any, Any, Any, Any]:
        missing: list[str] = []
        modules: list[Any] = []
        for import_name in ("numpy", "cv2", "librosa", "onnxruntime"):
            try:
                modules.append(__import__(import_name))
            except ImportError:
                missing.append(import_name)
        if missing:
            raise RuntimeError(
                "Missing optional Wav2Lip inference dependencies: " + ", ".join(missing)
            )
        return tuple(modules)  # type: ignore[return-value]

    @staticmethod
    def _detect_face(cv2: Any, frame: Any) -> tuple[int, int, int, int]:
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(str(cascade_path))
        if detector.empty():
            raise RuntimeError(f"Cannot load OpenCV face detector: {cascade_path}")
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = detector.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(40, 40),
        )
        if len(faces) == 0:
            raise ValueError("No frontal face detected in the source image")
        x, y, width, height = max(faces, key=lambda item: int(item[2]) * int(item[3]))
        frame_height, frame_width = frame.shape[:2]
        horizontal_padding = int(width * 0.08)
        top_padding = int(height * 0.08)
        bottom_padding = int(height * 0.18)
        x1 = max(0, int(x) - horizontal_padding)
        y1 = max(0, int(y) - top_padding)
        x2 = min(frame_width, int(x + width) + horizontal_padding)
        y2 = min(frame_height, int(y + height) + bottom_padding)
        return x1, y1, x2, y2

    def _extract_pcm_audio(self, source: Path, destination: Path) -> None:
        command = [
            self._ffmpeg_path(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
        self._run(command, "audio conversion")

    @staticmethod
    def _wav2lip_mel(np: Any, librosa: Any, audio_path: Path) -> Any:
        waveform, _ = librosa.load(str(audio_path), sr=16000, mono=True)
        if waveform.size == 0:
            raise ValueError("Audio stream is empty")
        preemphasized = np.append(waveform[0], waveform[1:] - 0.97 * waveform[:-1])
        spectrum = librosa.stft(
            y=preemphasized,
            n_fft=800,
            hop_length=200,
            win_length=800,
        )
        magnitude = np.abs(spectrum)
        mel_basis = librosa.filters.mel(
            sr=16000,
            n_fft=800,
            n_mels=80,
            fmin=55,
            fmax=7600,
        )
        mel = np.dot(mel_basis, magnitude)
        mel_db = 20.0 * np.log10(np.maximum(1e-5, mel)) - 20.0
        normalized = (8.0 * ((mel_db - -100.0) / 100.0)) - 4.0
        normalized = np.clip(normalized, -4.0, 4.0)
        if np.isnan(normalized).any():
            raise ValueError("Mel spectrogram contains NaN values")
        return normalized.astype(np.float32)

    def _split_mel(self, np: Any, mel: Any) -> list[Any]:
        mel_step_size = 16
        if mel.shape[1] < mel_step_size:
            mel = np.pad(mel, ((0, 0), (0, mel_step_size - mel.shape[1])), mode="edge")
        chunks: list[Any] = []
        index = 0
        multiplier = 80.0 / self.fps
        while True:
            start = int(index * multiplier)
            if start + mel_step_size >= mel.shape[1]:
                chunks.append(mel[:, -mel_step_size:])
                break
            chunks.append(mel[:, start : start + mel_step_size])
            index += 1
        return chunks

    def _render_frames(
        self,
        *,
        np: Any,
        cv2: Any,
        session: Any,
        source_frame: Any,
        face_box: tuple[int, int, int, int],
        mel_chunks: list[Any],
        destination: Path,
    ) -> None:
        frame_height, frame_width = source_frame.shape[:2]
        writer = cv2.VideoWriter(
            str(destination),
            cv2.VideoWriter_fourcc(*"MJPG"),
            self.fps,
            (frame_width, frame_height),
        )
        if not writer.isOpened():
            raise RuntimeError("OpenCV could not create the temporary video")
        x1, y1, x2, y2 = face_box
        try:
            for mel_chunk in mel_chunks:
                frame = source_frame.copy()
                face = frame[y1:y2, x1:x2]
                resized_face = cv2.resize(face, (96, 96))
                masked_face = resized_face.copy()
                masked_face[48:, :] = 0
                image_input = np.concatenate((masked_face, resized_face), axis=2)
                image_input = image_input.astype(np.float32) / 255.0
                image_input = np.transpose(image_input, (2, 0, 1))[None, ...]
                mel_input = mel_chunk[None, None, ...].astype(np.float32)
                feed = self._build_onnx_feed(session, image_input, mel_input)
                prediction = session.run(None, feed)[0]
                predicted_face = self._prediction_to_image(np, prediction)
                predicted_face = cv2.resize(predicted_face, (x2 - x1, y2 - y1))
                frame[y1:y2, x1:x2] = predicted_face
                writer.write(frame)
        finally:
            writer.release()

    @staticmethod
    def _build_onnx_feed(session: Any, image_input: Any, mel_input: Any) -> dict[str, Any]:
        feed: dict[str, Any] = {}
        for model_input in session.get_inputs():
            name = model_input.name
            lowered_name = name.lower()
            shape = model_input.shape
            if any(token in lowered_name for token in ("mel", "audio")) or (
                len(shape) == 4 and 80 in shape and 16 in shape
            ):
                feed[name] = mel_input
            elif any(token in lowered_name for token in ("video", "frame", "image", "face")):
                feed[name] = image_input
        if len(feed) != len(session.get_inputs()):
            input_names = [item.name for item in session.get_inputs()]
            if len(input_names) == 2:
                feed = {input_names[0]: mel_input, input_names[1]: image_input}
            else:
                raise RuntimeError(f"Unsupported ONNX input signature: {input_names}")
        return feed

    @staticmethod
    def _prediction_to_image(np: Any, prediction: Any) -> Any:
        output = np.asarray(prediction)
        if output.ndim != 4:
            raise RuntimeError(f"Unexpected ONNX output rank: {output.shape}")
        image = output[0]
        if image.shape[0] in (1, 3, 4):
            image = np.transpose(image, (1, 2, 0))
        if image.shape[-1] == 1:
            image = np.repeat(image, 3, axis=2)
        image = image[:, :, :3]
        if float(image.max()) <= 1.5:
            image = image * 255.0
        return np.clip(image, 0, 255).astype(np.uint8)

    def _mux_audio(self, video_path: Path, audio_path: Path, destination: Path) -> None:
        command = [
            self._ffmpeg_path(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-movflags",
            "+faststart",
            str(destination),
        ]
        self._run(command, "audio/video mux")

    def _fallback_static(self, face_path: Path, audio_path: Path, destination: Path) -> dict[str, Any]:
        common = [
            self._ffmpeg_path(),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-framerate",
            str(self.fps),
            "-i",
            str(face_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
        ]
        attempts = (
            ["-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage"],
            ["-c:v", "mpeg4", "-q:v", "3"],
        )
        errors: list[str] = []
        for encoder_args in attempts:
            command = common + encoder_args + [str(destination)]
            try:
                self._run(command, "static-avatar fallback")
                if destination.is_file() and destination.stat().st_size > 0:
                    return {
                        "ok": True,
                        "encoder": encoder_args[1],
                        "size_bytes": destination.stat().st_size,
                    }
                errors.append(f"{encoder_args[1]} created no output")
            except Exception as exc:
                errors.append(f"{encoder_args[1]}: {exc}")
        return {"ok": False, "error": " | ".join(errors)}

    def _ffmpeg_path(self) -> str:
        resolved = shutil.which(self.ffmpeg_binary)
        if not resolved:
            raise FileNotFoundError(f"FFmpeg executable not found: {self.ffmpeg_binary}")
        return resolved

    @staticmethod
    def _run(command: list[str], purpose: str) -> None:
        completed = subprocess.run(command, capture_output=True, check=False)
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"{purpose} failed ({completed.returncode}): {stderr[-1500:]}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wav2Lip ONNX integration prototype")
    parser.add_argument("face", nargs="?", help="source face image")
    parser.add_argument("audio", nargs="?", help="driving audio")
    parser.add_argument("destination", nargs="?", help="output MP4")
    parser.add_argument(
        "--download-model",
        action="store_true",
        help="allow downloading the approximately 145 MB ONNX model",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    provider = Wav2LipProvider(auto_download=args.download_model)
    if args.download_model and not (args.face and args.audio and args.destination):
        print(json.dumps(provider.download_model(), ensure_ascii=False, indent=2))
        return 0
    if not (args.face and args.audio and args.destination):
        raise SystemExit("face, audio and destination are required unless only --download-model is used")
    result = provider.synthesize(args.face, args.audio, args.destination)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
