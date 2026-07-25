import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from providers.base import ProviderError
from providers.avatar.wav2lip_onnx import (
    AVATAR_CLONE_PREFIX,
    DEFAULT_MODEL_DIR,
    Wav2LipONNXAvatarProvider,
    build_wav2lip_provider,
)


class _FakePng:
    def __init__(self, size=2048):
        # Minimal valid PNG header so size check passes
        self.bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * max(0, size - 8)


def _make_wav_bytes(seconds=2):
    # 16kHz mono PCM s16le = 32000 bytes/sec -> not used; we just need a non-empty wav body
    return b"RIFF" + (32000 * seconds).to_bytes(4, "little") + b"WAVE" + b"\x00" * (seconds * 64)


class Wav2LipONNXProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.face = Path(self.tmp.name) / "face.png"
        _FakePng(2048).bytes and self.face.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 2040)
        self.audio = Path(self.tmp.name) / "audio.wav"
        self.audio.write_bytes(_make_wav_bytes(1))
        self.dest = Path(self.tmp.name) / "out.mp4"

    def tearDown(self):
        self.tmp.cleanup()

    def test_constructor_uses_default_model_path(self):
        p = Wav2LipONNXAvatarProvider()
        # Path may be DEFAULT_MODEL_DIR/wav2lip.onnx or env override
        self.assertTrue(str(p._impl.model_path).endswith("wav2lip.onnx"))

    def test_clone_prefix_constant(self):
        self.assertEqual(AVATAR_CLONE_PREFIX, "avatar:")

    def test_factory_shortcut(self):
        p = build_wav2lip_provider(model_path=str(self.dest))
        self.assertEqual(p.name, "wav2lip_onnx")

    def test_synthesize_propagates_failure(self):
        provider = Wav2LipONNXAvatarProvider(model_path=str(Path(self.tmp.name) / "missing.onnx"))
        fake = {"status": "failed", "mode": "none", "reason": "boom", "output_path": str(self.dest)}
        with patch.object(provider._impl, "synthesize", return_value=fake):
            with self.assertRaises(ProviderError) as ctx:
                provider.synthesize(self.face, self.audio, self.dest)
        self.assertIn("boom", str(ctx.exception))

    def test_synthesize_propagates_missing_face(self):
        provider = Wav2LipONNXAvatarProvider(model_path=str(Path(self.tmp.name) / "missing.onnx"))
        with self.assertRaises(ProviderError):
            provider.synthesize(Path(self.tmp.name) / "nope.png", self.audio, self.dest)

    def test_synthesize_propagates_missing_audio(self):
        provider = Wav2LipONNXAvatarProvider(model_path=str(Path(self.tmp.name) / "missing.onnx"))
        with self.assertRaises(ProviderError):
            provider.synthesize(self.face, Path(self.tmp.name) / "nope.wav", self.dest)

    def test_synthesize_static_fallback_returns_success(self):
        provider = Wav2LipONNXAvatarProvider(model_path=str(Path(self.tmp.name) / "missing.onnx"))
        fake = {
            "status": "success",
            "mode": "static_avatar",
            "output_path": str(self.dest),
            "model_present": False,
            "fallback_used": True,
            "elapsed_seconds": 0.42,
        }
        with patch.object(provider._impl, "synthesize", return_value=fake) as m:
            result = provider.synthesize(self.face, self.audio, self.dest)
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["mode"], "static_avatar")
        self.assertEqual(result["provider"], "wav2lip_onnx")

    def test_synthesize_onnx_result_is_not_reported_as_fallback(self):
        provider = Wav2LipONNXAvatarProvider(model_path=str(Path(self.tmp.name) / "wav2lip.onnx"))
        fake = {
            "status": "success",
            "mode": "wav2lip_onnx",
            "output_path": str(self.dest),
            "model_present": True,
            "fallback_used": False,
            "elapsed_seconds": 73.116,
        }
        with patch.object(provider._impl, "synthesize", return_value=fake):
            result = provider.synthesize(self.face, self.audio, self.dest)
        self.assertEqual(result["mode"], "wav2lip_onnx")
        self.assertFalse(result["fallback_used"])
        self.assertTrue(result["model_present"])

    def test_healthcheck_returns_structured_dict(self):
        provider = Wav2LipONNXAvatarProvider(model_path=str(Path(self.tmp.name) / "missing.onnx"))
        info = provider.healthcheck()
        self.assertIn("model_present", info)
        self.assertIn("dependencies_ok", info)
        self.assertIn("ffmpeg_available", info)
        self.assertIn("dependency_warnings", info)
        self.assertIn("latency_ms", info)
        self.assertEqual(info["provider"], "wav2lip_onnx")

    def test_default_model_dir_set(self):
        self.assertTrue(str(DEFAULT_MODEL_DIR).endswith("wav2lip"))

    def test_unicode_face_path_uses_imdecode(self):
        provider = Wav2LipONNXAvatarProvider(model_path=str(Path(self.tmp.name) / "missing.onnx"))
        unicode_face = Path(self.tmp.name) / "中文头像.png"
        unicode_face.write_bytes(self.face.read_bytes())
        fake_numpy = MagicMock()
        fake_numpy.uint8 = "uint8"
        fake_cv2 = MagicMock()
        fake_cv2.IMREAD_COLOR = 1
        fake_cv2.imdecode.return_value = None
        fake_librosa = MagicMock()
        fake_ort = MagicMock()
        fake_ort.SessionOptions.return_value = MagicMock()
        fake_ort.GraphOptimizationLevel.ORT_ENABLE_ALL = 99
        fake_ort.InferenceSession.return_value = MagicMock()
        with patch.object(
            provider._impl,
            "_load_inference_dependencies",
            return_value=(fake_numpy, fake_cv2, fake_librosa, fake_ort),
        ), patch.object(fake_numpy, "fromfile", return_value=b"image-bytes") as fromfile:
            with self.assertRaisesRegex(ValueError, "cannot read face image"):
                provider._impl._synthesize_onnx(unicode_face, self.audio, self.dest)
        fromfile.assert_called_once_with(str(unicode_face.resolve()), dtype="uint8")
        fake_cv2.imdecode.assert_called_once_with(b"image-bytes", 1)
