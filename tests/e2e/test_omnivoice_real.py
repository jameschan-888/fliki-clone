"""P8-OmniVoice: 真接口 e2e (需要 docker Desktop + ghcr.io/debpalash/omnivoice-studio:latest 已起).

启动 (沙箱外人工执行):
  docker run -d --name omnivoice -p 127.0.0.1:3900:3900 \\
    -e HF_ENDPOINT=https://hf-mirror.com -e HF_HUB_DISABLE_XET=1 \\
    -e OMNIVOICE_TTS_BACKEND=kittentts \\
    -v D:/workspace/docker-volumes/omnivoice-data:/app/omnivoice_data \\
    ghcr.io/debpalash/omnivoice-studio:latest

跑这个测试:
  OMNIVOICE_E2E=1 OMNIVOICE_MODEL=kittentts python -m unittest tests.e2e.test_omnivoice_real -v

跳过 (沙箱里 docker 受限):
  python -m unittest tests.e2e.test_omnivoice_real -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


@unittest.skipUnless(os.getenv("OMNIVOICE_E2E") == "1", "set OMNIVOICE_E2E=1 to enable real-interface test")
class OmniVoiceRealE2ETest(unittest.TestCase):
    def test_health(self):
        import httpx
        base_url = os.getenv("OMNIVOICE_BASE_URL", "http://127.0.0.1:3900").rstrip("/")
        resp = httpx.get(f"{base_url}/health", timeout=10.0)
        self.assertEqual(resp.status_code, 200, f"health failed: {resp.text[:200]}")

    def test_synthesize_minimum_audio(self):
        from providers.tts.omnivoice_tts import OmniVoiceTTSProvider
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            provider = OmniVoiceTTSProvider(timeout=120.0)
            result = provider.synthesize("hello world", out, voice="alloy")
            self.assertGreater(result["bytes"], 1024, "real audio should be > 1KB")
            self.assertTrue(out.exists() and out.stat().st_size > 1024)
        finally:
            out.unlink(missing_ok=True)

    def test_fallback_chain_real(self):
        from providers.tts import synthesize_tts_with_fallback
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            result = synthesize_tts_with_fallback(
                "real e2e fallback test",
                out,
                voice="omnivoice:alloy",
                prefer="auto",
            )
            self.assertIn(result["tts_provider"], ("omnivoice", "edge_tts"))
        finally:
            out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
