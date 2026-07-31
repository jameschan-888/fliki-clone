"""P8-OmniVoice: TTS provider 单元测试 (mock HTTP + 真接口)."""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from providers.base import ProviderError as _ProviderError
from providers.tts.omnivoice_tts import (
    OmniVoiceTTSProvider,
    OmniVoiceTTSError,
    is_omnivoice_voice,
    build_omnivoice_provider,
    _resolve_voice,
)


def test_resolve_voice():
    """_resolve_voice 协议解析."""
    assert _resolve_voice(None) == "alloy", "None should default to alloy"
    assert _resolve_voice("zh-CN-XiaoxiaoNeural") == "zh-CN-XiaoxiaoNeural"
    assert _resolve_voice("omnivoice:zh_female_1") == "zh_female_1"
    assert _resolve_voice("omnivoice:kokoro:zh_female_1") == "zh_female_1", "should take last segment"
    assert _resolve_voice("omnivoice:") == "alloy", "empty voice_id falls back"
    print(f"  resolve: alloy | omnivoice:zh_female_1 | omnivoice:kokoro:zh_female_1 OK")


def test_is_omnivoice_voice():
    """voice 前缀检测."""
    assert is_omnivoice_voice("omnivoice:zh_female_1") is True
    assert is_omnivoice_voice("omnivoice:") is True
    assert is_omnivoice_voice("zh-CN-XiaoxiaoNeural") is False
    assert is_omnivoice_voice(None) is False
    assert is_omnivoice_voice("") is False
    print("  prefix detection OK")


def test_detect_provider_omnivoice():
    """voice 带 omnivoice: 前缀应被 detect_provider_for_voice 识别."""
    from providers.tts import detect_provider_for_voice
    assert detect_provider_for_voice("omnivoice:zh_female_1") == "omnivoice"
    assert detect_provider_for_voice("zh-CN-XiaoxiaoNeural") == "edge_tts"
    assert detect_provider_for_voice("minimax-clone:xxx") == "minimax"
    assert detect_provider_for_voice(None) == "edge_tts"
    print("  detect routing OK")


def test_synthesize_connect_error():
    """OmniVoice 不可达时应抛 OmniVoiceTTSError + 友好提示."""
    import httpx
    provider = OmniVoiceTTSProvider(base_url="http://127.0.0.1:1", timeout=5.0)  # port 1 肯定不可达
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        try:
            provider.synthesize("hello", out, voice="omnivoice:zh_female_1")
            assert False, "should raise"
        except OmniVoiceTTSError as exc:
            msg = str(exc)
            assert "OmniVoice unreachable" in msg
            assert "docker run" in msg, "should hint at docker run command"
            print(f"  connect error message OK ({len(msg)} chars)")
    finally:
        out.unlink(missing_ok=True)


def test_synthesize_mock_200():
    """模拟 OmniVoice 200 响应, 验证写入和返回值."""
    import httpx
    fake_audio = b"\xff\xfb" + b"\x00" * 1024  # fake mp3 bytes

    def mock_post(self, url, json=None, headers=None, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = fake_audio
        resp.text = ""
        return resp

    with patch("httpx.Client.post", mock_post):
        provider = OmniVoiceTTSProvider(base_url="http://fake:3900", timeout=5.0)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            result = provider.synthesize("test text", out, voice="omnivoice:zh_female_1")
            assert result["provider"] == "omnivoice"
            assert result["voice"] == "zh_female_1"
            assert result["bytes"] == len(fake_audio)
            assert out.exists() and out.stat().st_size == len(fake_audio)
            print(f"  synthesize 200 OK: {result}")
        finally:
            out.unlink(missing_ok=True)


def test_synthesize_500():
    """OmniVoice 5xx 应抛 OmniVoiceTTSError."""
    def mock_post(self, url, json=None, headers=None, **kwargs):
        resp = MagicMock()
        resp.status_code = 500
        resp.content = b""
        resp.text = "internal server error"
        return resp

    with patch("httpx.Client.post", mock_post):
        provider = OmniVoiceTTSProvider(base_url="http://fake:3900", timeout=5.0)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            try:
                provider.synthesize("test", out)
                assert False, "should raise"
            except OmniVoiceTTSError as exc:
                assert "500" in str(exc)
                assert "internal" in str(exc)
                print(f"  500 error: {exc}")
        finally:
            out.unlink(missing_ok=True)


def test_synthesize_too_small():
    """返回 audio < 256 字节应判为可疑, 抛错."""
    def mock_post(self, url, json=None, headers=None, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"x" * 100
        resp.text = ""
        return resp

    with patch("httpx.Client.post", mock_post):
        provider = OmniVoiceTTSProvider(base_url="http://fake:3900", timeout=5.0)
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            try:
                provider.synthesize("test", out)
                assert False, "should raise"
            except OmniVoiceTTSError as exc:
                assert "suspiciously small" in str(exc)
                print(f"  small audio rejected: {exc}")
        finally:
            out.unlink(missing_ok=True)


def test_synthesize_empty_text():
    """空文本应抛错."""
    provider = OmniVoiceTTSProvider(base_url="http://fake:3900", timeout=5.0)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        try:
            provider.synthesize("", out)
            assert False, "should raise"
        except OmniVoiceTTSError as exc:
            assert "non-empty" in str(exc)
            print(f"  empty text rejected: {exc}")
    finally:
        out.unlink(missing_ok=True)


def test_fallback_chain_includes_omnivoice():
    """synthesize_tts_with_fallback 应在 omnivoice 前缀时尝试 omnivoice."""
    from providers.tts import synthesize_tts_with_fallback, OMNIVOICE_VOICE_NAME
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        # mock omnivoice 抛错, 应该 fallback 到 edge_tts
        with patch("providers.tts.omnivoice_tts.OmniVoiceTTSProvider.synthesize",
                   side_effect=OmniVoiceTTSError("mocked unavailable")):
            result = synthesize_tts_with_fallback(
                "test fallback",
                out,
                voice="omnivoice:zh_female_1",
                prefer="auto",
            )
            assert result["tts_provider"] == "edge_tts", f"expected fallback to edge_tts, got {result['tts_provider']}"
            assert "omnivoice: mocked unavailable" in result.get("fallback_errors", [""])[0]
            print(f"  omnivoice fail -> edge_tts fallback OK")
    finally:
        out.unlink(missing_ok=True)


def test_fallback_chain_omnivoice_success():
    """omnivoice 成功时优先返回 omnivoice 结果."""
    from providers.tts import synthesize_tts_with_fallback, OMNIVOICE_VOICE_NAME
    fake_audio = b"\xff\xfb" + b"\x00" * 1024

    def mock_synth(self, text, destination, voice=None, **kwargs):
        destination.write_bytes(fake_audio)
        return {"provider": "omnivoice", "voice": "zh_female_1", "local_path": str(destination), "bytes": len(fake_audio)}

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        out = Path(tmp.name)
    try:
        with patch("providers.tts.omnivoice_tts.OmniVoiceTTSProvider.synthesize", mock_synth):
            result = synthesize_tts_with_fallback(
                "test",
                out,
                voice="omnivoice:zh_female_1",
                prefer="auto",
            )
            assert result["tts_provider"] == "omnivoice", f"expected omnivoice, got {result['tts_provider']}"
            print(f"  omnivoice success: {result}")
    finally:
        out.unlink(missing_ok=True)


def test_build_omnivoice_provider_from_env():
    """环境变量驱动的工厂."""
    import os
    os.environ["OMNIVOICE_BASE_URL"] = "http://test:3900"
    os.environ["OMNIVOICE_API_KEY"] = "test-key-123"
    provider = build_omnivoice_provider()
    assert provider.base_url == "http://test:3900"
    assert provider.api_key == "test-key-123"
    print(f"  env factory OK: {provider.base_url} key={'set' if provider.api_key else 'none'}")


if __name__ == "__main__":
    test_resolve_voice()
    test_is_omnivoice_voice()
    test_detect_provider_omnivoice()
    test_synthesize_connect_error()
    test_synthesize_mock_200()
    test_synthesize_500()
    test_synthesize_too_small()
    test_synthesize_empty_text()
    test_fallback_chain_includes_omnivoice()
    test_fallback_chain_omnivoice_success()
    test_build_omnivoice_provider_from_env()
    print("ALL PASS")
