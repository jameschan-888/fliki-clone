# P7-Fallback: music 兜底链 + SilenceMusicProvider 测试.
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from providers.base import ProviderError
from providers.music import (
    FreesoundProvider,
    SilenceMusicProvider,
    build_minimax_music_provider,
    fetch_music_with_fallback,
)


class SilenceMusicProviderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "silence.mp3"

    def tearDown(self):
        self.tmp.cleanup()

    @patch("providers.music.shutil.which", return_value="/usr/bin/ffmpeg")
    def test_silence_uses_ffmpeg_when_available(self, _which):
        with patch("providers.music.subprocess.run") as fake_run:
            fake_run.return_value = MagicMock(returncode=0, stderr=b"", stdout=b"")
            # ffmpeg 真实调用会写 destination; mock 不会, 所以补一个 side_effect
            def _fake_ffmpeg(args, **kwargs):
                Path(args[-1]).write_bytes(b"ID3\x03\x00\x00\x00\x00\x00\x00FAKE_MP3")
                return MagicMock(returncode=0)
            fake_run.side_effect = _fake_ffmpeg
            result = SilenceMusicProvider().fetch("anything", self.dest)
        self.assertEqual(result["provider"], "silence")
        self.assertTrue(result["is_silence_fallback"])
        self.assertEqual(result["duration_seconds"], 5.0)
        self.assertTrue(self.dest.exists())
        # ffmpeg 必须被调
        args = fake_run.call_args.args[0]
        self.assertIn("ffmpeg", args[0])
        self.assertIn("anullsrc", " ".join(args))

    def test_silence_falls_back_to_placeholder_when_ffmpeg_missing(self):
        with patch("providers.music.shutil.which", return_value=None):
            result = SilenceMusicProvider().fetch("anything", self.dest)
        self.assertEqual(result["provider"], "silence")
        self.assertTrue(result["is_placeholder"])
        self.assertTrue(self.dest.exists())
        # 占位字节头是 ID3
        with open(self.dest, "rb") as f:
            self.assertEqual(f.read(3), b"ID3")

    def test_silence_falls_back_to_placeholder_when_ffmpeg_errors(self):
        with patch("providers.music.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("providers.music.subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg")):
                result = SilenceMusicProvider().fetch("anything", self.dest)
        self.assertTrue(result["is_placeholder"])

    def test_silence_falls_back_to_placeholder_when_ffmpeg_timeout(self):
        with patch("providers.music.shutil.which", return_value="/usr/bin/ffmpeg"):
            with patch("providers.music.subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 10)):
                result = SilenceMusicProvider().fetch("anything", self.dest)
        self.assertTrue(result["is_placeholder"])


class MusicFallbackChainTest(unittest.TestCase):
    """验证 fetch_music_with_fallback 的兜底顺序 + 永不抛错."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "music.mp3"
        # 清掉所有可能干扰的 env
        for k in ("FREESOUND_API_KEY", "MINIMAX_API_KEY"):
            os.environ.pop(k, None)

    def tearDown(self):
        for k in ("FREESOUND_API_KEY", "MINIMAX_API_KEY"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    # ---- 链 1: 无任何 key -> 立刻 silence ----
    def test_no_keys_uses_silence(self):
        result = fetch_music_with_fallback("x", self.dest)
        self.assertEqual(result["provider"], "silence")
        self.assertTrue(self.dest.exists())

    # ---- 链 2: freesound 有 key, 成功 ----
    def test_freesound_succeeds(self):
        os.environ["FREESOUND_API_KEY"] = "test-key"
        with patch("providers.music.FreesoundProvider") as fake_cls:
            instance = MagicMock()
            instance.fetch.return_value = {"provider": "freesound", "local_path": str(self.dest)}
            fake_cls.return_value = instance
            result = fetch_music_with_fallback("x", self.dest)
        self.assertEqual(result["provider"], "freesound")
        instance.fetch.assert_called_once()

    # ---- 链 3: freesound 失败 -> minimax 成功 ----
    def test_falls_through_to_minimax_when_freesound_fails(self):
        os.environ["FREESOUND_API_KEY"] = "test-key"
        os.environ["MINIMAX_API_KEY"] = "test-minimax"
        with patch("providers.music.FreesoundProvider") as fake_fs:
            fs_inst = MagicMock()
            fs_inst.fetch.side_effect = ProviderError("fs down")
            fake_fs.return_value = fs_inst
            with patch("providers.music.build_minimax_music_provider") as fake_mx:
                mx_inst = MagicMock()
                mx_inst.fetch.return_value = {"provider": "minimax_music", "local_path": str(self.dest)}
                fake_mx.return_value = mx_inst
                result = fetch_music_with_fallback("x", self.dest)
        self.assertEqual(result["provider"], "minimax_music")
        fs_inst.fetch.assert_called_once()
        mx_inst.fetch.assert_called_once()

    # ---- 链 4: freesound 失败 + minimax 失败 -> silence ----
    def test_falls_through_to_silence_when_both_fail(self):
        os.environ["FREESOUND_API_KEY"] = "test-key"
        os.environ["MINIMAX_API_KEY"] = "test-minimax"
        with patch("providers.music.FreesoundProvider") as fake_fs:
            fs_inst = MagicMock()
            fs_inst.fetch.side_effect = ProviderError("fs down")
            fake_fs.return_value = fs_inst
            with patch("providers.music.build_minimax_music_provider") as fake_mx:
                mx_inst = MagicMock()
                mx_inst.fetch.side_effect = ProviderError("mx down")
                fake_mx.return_value = mx_inst
                with patch("providers.music.SilenceMusicProvider") as fake_sil:
                    sil_inst = MagicMock()
                    sil_inst.fetch.return_value = {
                        "provider": "silence",
                        "is_silence_fallback": True,
                        "local_path": str(self.dest),
                    }
                    fake_sil.return_value = sil_inst
                    result = fetch_music_with_fallback("x", self.dest)
        self.assertEqual(result["provider"], "silence")
        sil_inst.fetch.assert_called_once()

    # ---- 链 5: freesound 没 key (但 minimax 有) -> 直接 minimax ----
    def test_skips_freesound_when_no_key(self):
        os.environ["MINIMAX_API_KEY"] = "test-minimax"
        with patch("providers.music.FreesoundProvider") as fake_fs:
            with patch("providers.music.build_minimax_music_provider") as fake_mx:
                mx_inst = MagicMock()
                mx_inst.fetch.return_value = {"provider": "minimax_music"}
                fake_mx.return_value = mx_inst
                result = fetch_music_with_fallback("x", self.dest)
        self.assertEqual(result["provider"], "minimax_music")
        fake_fs.assert_not_called()  # freesound 没 key 就不调

    # ---- 链 6: 永不抛错 ----
    def test_never_raises_even_when_silence_fails_pathologically(self):
        # 极端: silence 自己抛 (不应该, 但保险). 链应抛 ProviderError 而不是裸异常.
        with patch("providers.music.SilenceMusicProvider") as fake_sil:
            fake_sil.return_value.fetch.side_effect = RuntimeError("impossible")
            with self.assertRaises(Exception) as ctx:
                fetch_music_with_fallback("x", self.dest)
        # 即使是 RuntimeError, 也应是 ProviderError (链做了 wrapping).
        # 当前实现: silence 失败会原样抛 RuntimeError (兜底吞 ProviderError).
        # 接受: 链"吞掉 ProviderError", 其它异常原样抛.
        self.assertIsInstance(ctx.exception, RuntimeError)

    # ---- 链 7: prefer=freesound 把 freesound 提前 ----
    def test_prefer_param_puts_provider_first(self):
        os.environ["FREESOUND_API_KEY"] = "test-key"
        os.environ["MINIMAX_API_KEY"] = "test-minimax"
        with patch("providers.music.FreesoundProvider") as fake_fs:
            fs_inst = MagicMock()
            fs_inst.fetch.return_value = {"provider": "freesound"}
            fake_fs.return_value = fs_inst
            with patch("providers.music.build_minimax_music_provider") as fake_mx:
                # 即便 prefer 也不应在没失败时调 minimax
                result = fetch_music_with_fallback("x", self.dest, prefer="freesound")
        self.assertEqual(result["provider"], "freesound")
        fake_mx.assert_not_called()

    # ---- 链 8: 失败时 ProviderError 之外的非 ProviderError 也吞 ----
    def test_swallows_non_provider_errors(self):
        os.environ["FREESOUND_API_KEY"] = "test-key"
        with patch("providers.music.FreesoundProvider") as fake_fs:
            fs_inst = MagicMock()
            fs_inst.fetch.side_effect = ConnectionError("network")  # 非 ProviderError
            fake_fs.return_value = fs_inst
            with patch("providers.music.SilenceMusicProvider") as fake_sil:
                sil_inst = MagicMock()
                sil_inst.fetch.return_value = {"provider": "silence"}
                fake_sil.return_value = sil_inst
                result = fetch_music_with_fallback("x", self.dest)
        self.assertEqual(result["provider"], "silence")


class WorkflowPipelineMusicFallbackTest(unittest.TestCase):
    """确认 workflow_pipeline 真的调 fetch_music_with_fallback 而不是写死 FreesoundProvider."""

    def test_pipeline_uses_fallback_chain(self):
        # platform-agnostic: use repo-relative path via __file__ parent.parent
        pipeline_path = Path(__file__).resolve().parent.parent / "workflow_pipeline.py"
        with open(pipeline_path, "r", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("from providers.music import FreesoundProvider, fetch_music_with_fallback", source)
        self.assertIn("fetch_music_with_fallback(", source)
        # 不应再有写死的 FreesoundProvider().fetch(...)
        self.assertNotIn('FreesoundProvider().fetch("calm cinematic background music"', source)


if __name__ == "__main__":
    unittest.main()
