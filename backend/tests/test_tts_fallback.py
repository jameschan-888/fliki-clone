# P7-Fallback: TTS 兜底链 + 跟 pipeline 集成测试.
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from providers.base import ProviderError
from providers.tts import (
    DEFAULT_VOICE,
    MINIMAX_CLONE_PREFIX,
    EdgeTTSProvider,
    build_minimax_provider,
    synthesize_tts_with_fallback,
)


# (edge_tts real-call tests replaced with mock for speed; edge_tts lib itself is covered by upstream tests)



class TTSFallbackChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dest = Path(self.tmp.name) / "out.mp3"
        for k in ("MINIMAX_API_KEY", "EDGE_TTS_VOICE"):
            os.environ.pop(k, None)
        # 全局 mock EdgeTTSProvider, 真实 edge_tts 联网太慢 (3-5s/次)
        from providers.tts import EdgeTTSProvider
        self._edge_synthesize = EdgeTTSProvider.synthesize
        def _fake_synthesize(self, text, destination, voice=DEFAULT_VOICE):
            destination = Path(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"ID3" + b"\x03" + b"\x00" * 1024)
            return {"provider": "edge_tts", "voice": voice, "local_path": str(destination), "bytes": 1027}
        EdgeTTSProvider.synthesize = _fake_synthesize

    def tearDown(self):
        from providers.tts import EdgeTTSProvider
        EdgeTTSProvider.synthesize = self._edge_synthesize
        for k in ("MINIMAX_API_KEY", "EDGE_TTS_VOICE"):
            os.environ.pop(k, None)
        self.tmp.cleanup()

    # ---- 链 1: voice 是 minimax-clone + key -> minimax 成功 ----
    def test_minimax_clone_with_key_uses_minimax(self):
        os.environ["MINIMAX_API_KEY"] = "test-key"
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            provider = MagicMock()
            provider.synthesize_with_voice_id.return_value = {
                "provider": "minimax",
                "voice": "fliki_abc",
                "local_path": str(self.dest),
                "bytes": 1024,
            }
            fake_bp.return_value = provider
            result = synthesize_tts_with_fallback(
                "hi",
                self.dest,
                voice=f"{MINIMAX_CLONE_PREFIX}fliki_abc",
            )
        self.assertEqual(result["tts_provider"], "minimax")
        provider.synthesize_with_voice_id.assert_called_once()
        # 验证传进去的 voice_id 是去前缀的
        kwargs = provider.synthesize_with_voice_id.call_args
        self.assertEqual(kwargs.args[2], "fliki_abc")

    # ---- 链 2: voice 是 minimax-clone + key + minimax 失败 -> edge 兜底 ----
    def test_minimax_failure_falls_through_to_edge(self):
        # 真实 edge_tts 不在这里跑 (3-5s/次), 用 mock 验证兜底链逻辑.
        os.environ["MINIMAX_API_KEY"] = "test-key"
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            provider = MagicMock()
            provider.synthesize_with_voice_id.side_effect = ProviderError("MiniMax 401")
            fake_bp.return_value = provider
            result = synthesize_tts_with_fallback(
                "你好世界",
                self.dest,
                voice=f"{MINIMAX_CLONE_PREFIX}fliki_abc",
            )
        # 兜底成功 -> edge_tts
        self.assertEqual(result["tts_provider"], "edge_tts")
        self.assertEqual(result["provider"], "edge_tts")
        self.assertTrue(self.dest.exists())
        self.assertGreater(self.dest.stat().st_size, 512)
        # fallback_errors 应记录 minimax 失败原因
        self.assertIn("fallback_errors", result)
        self.assertIn("MiniMax 401", result["fallback_errors"][0])

    # ---- 链 3: voice 是 Edge short_name -> 直接 edge ----
    def test_edge_short_name_uses_edge_directly(self):
        # 真实 edge_tts 不在这里跑 (3-5s/次), 用 mock 验证兜底链逻辑.
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            result = synthesize_tts_with_fallback(
                "你好",
                self.dest,
                voice="zh-CN-XiaoxiaoNeural",
            )
        # minimax 完全不该被尝试
        fake_bp.assert_not_called()
        self.assertEqual(result["tts_provider"], "edge_tts")
        self.assertEqual(result["provider"], "edge_tts")
        self.assertTrue(self.dest.exists())

    # ---- 链 4: voice=None -> 直接 edge ----
    def test_no_voice_uses_edge_default(self):
        # 真实 edge_tts 不在这里跑 (3-5s/次), 用 mock 验证兜底链逻辑.
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            result = synthesize_tts_with_fallback("hi", self.dest)
        fake_bp.assert_not_called()
        self.assertEqual(result["tts_provider"], "edge_tts")
        self.assertTrue(self.dest.exists())

    # ---- 链 5: voice 是 minimax-clone 但没 key -> 直接 edge ----
    def test_minimax_clone_without_key_skips_minimax(self):
        # 真实 edge_tts 不在这里跑 (3-5s/次), 用 mock 验证兜底链逻辑.
        os.environ.pop("MINIMAX_API_KEY", None)
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            result = synthesize_tts_with_fallback(
                "hi",
                self.dest,
                voice=f"{MINIMAX_CLONE_PREFIX}fliki_abc",
            )
        # 没 key 就不尝试 minimax
        fake_bp.assert_not_called()
        self.assertEqual(result["tts_provider"], "edge_tts")
        # voice 是 minimax-clone 形式, edge 兜底用默认 voice
        self.assertEqual(result["voice"], "zh-CN-XiaoxiaoNeural")
        self.assertTrue(self.dest.exists())

    # ---- 链 6: voice_cache 注入 minimax 不调 upload ----
    def test_voice_cache_seeds_provider(self):
        os.environ["MINIMAX_API_KEY"] = "test-key"
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            provider = MagicMock()
            provider.load_cache = MagicMock()
            provider.synthesize_with_voice_id.return_value = {
                "provider": "minimax",
                "voice": "fliki_xyz",
                "local_path": str(self.dest),
            }
            fake_bp.return_value = provider
            synthesize_tts_with_fallback(
                "hi",
                self.dest,
                voice=f"{MINIMAX_CLONE_PREFIX}fliki_xyz",
                voice_cache={"sha_xyz": "fliki_xyz"},
            )
        # load_cache 应被调
        provider.load_cache.assert_called_once_with({"sha_xyz": "fliki_xyz"})

    # ---- 链 7: 空文本 raise ----
    def test_empty_text_raises(self):
        with self.assertRaises(ProviderError):
            synthesize_tts_with_fallback("   ", self.dest, voice="anything")

    # ---- 链 8: 永不抛错 (除空文本) ----
    def test_never_raises_when_edge_also_succeeds(self):
        # 真实 edge_tts 不在这里跑 (3-5s/次), 用 mock 验证兜底链逻辑.
        os.environ["MINIMAX_API_KEY"] = "test-key"
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            provider = MagicMock()
            # minimax 抛非 ProviderError (网络错)
            provider.synthesize_with_voice_id.side_effect = ConnectionError("net down")
            fake_bp.return_value = provider
            # 不应抛, edge 兜底
            result = synthesize_tts_with_fallback(
                "hi",
                self.dest,
                voice=f"{MINIMAX_CLONE_PREFIX}fliki_abc",
            )
        self.assertEqual(result["tts_provider"], "edge_tts")
        self.assertIn("net down", result["fallback_errors"][0])

    # ---- 链 9: prefer=minimax 强制 minimax 路径 ----
    def test_prefer_minimax_forces_chain(self):
        os.environ["MINIMAX_API_KEY"] = "test-key"
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            provider = MagicMock()
            provider.synthesize_with_voice_id.return_value = {
                "provider": "minimax",
                "voice": "anything",
                "local_path": str(self.dest),
            }
            fake_bp.return_value = provider
            # voice 是 edge short_name, 但 prefer=minimax 强制走 minimax
            result = synthesize_tts_with_fallback(
                "hi",
                self.dest,
                voice="zh-CN-XiaoxiaoNeural",
                prefer="minimax",
            )
        self.assertEqual(result["tts_provider"], "minimax")

    # ---- 链 10: edge 路径错误时也兜底 (返回 error) ----
    def test_minimax_clone_prefix_variants(self):
        # 旧前缀 minimax_clone: 也要支持
        # 真实 edge_tts 不在这里跑 (3-5s/次), 用 mock 验证兜底链逻辑.
        os.environ["MINIMAX_API_KEY"] = "test-key"
        with patch("providers.tts.build_minimax_provider") as fake_bp:
            provider = MagicMock()
            provider.synthesize_with_voice_id.return_value = {
                "provider": "minimax",
                "voice": "fliki_legacy",
                "local_path": str(self.dest),
            }
            fake_bp.return_value = provider
            result = synthesize_tts_with_fallback(
                "hi",
                self.dest,
                voice="minimax_clone:fliki_legacy",
            )
        self.assertEqual(result["tts_provider"], "minimax")


class WorkflowPipelineTTSFallbackTest(unittest.TestCase):
    """确认 workflow_pipeline 真的调 synthesize_tts_with_fallback 而不是写死 EdgeTTSProvider."""

    def test_pipeline_uses_fallback_chain(self):
        with open("D:\\workspace\\Fliki视频制作还原\\backend\\workflow_pipeline.py", "r", encoding="utf-8") as f:
            source = f.read()
        self.assertIn("from providers.tts import DEFAULT_VOICE, EdgeTTSProvider, synthesize_tts_with_fallback", source)
        self.assertIn("synthesize_tts_with_fallback(", source)
        # TTS 节点标签应从 edge_tts 改 tts_chain
        self.assertIn('("tts_chain",synthesize_tts_with_fallback(', source)
        # 不应再有写死的 EdgeTTSProvider().synthesize(scene[ 旧调用
        self.assertNotIn('("edge_tts",synthesize_scene_voice(', source)


if __name__ == "__main__":
    unittest.main()
