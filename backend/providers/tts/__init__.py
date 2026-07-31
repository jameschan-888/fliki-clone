import asyncio
import os
from pathlib import Path
import edge_tts

from providers.base import ProviderError,TTSProvider

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class EdgeTTSProvider(TTSProvider):
    name="edge_tts"
    def synthesize(self,text,destination,voice=DEFAULT_VOICE):
        destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
        async def run(): await edge_tts.Communicate(text,voice).save(str(destination))
        asyncio.run(run())
        if not destination.exists() or destination.stat().st_size < 512: raise ProviderError("Edge TTS returned empty audio")
        return {"provider":self.name,"voice":voice,"local_path":str(destination)}



# ===== P5D-3 GPT-SoVITS HTTP adapter =====
from .gpt_sovits import GPTSoVITSProvider, GPTSoVITSError  # noqa: F401

GPT_SOVITS_CLONE_PREFIX = "clone:"
EDGE_VOICE_NAME = "edge_tts"
GPT_SOVITS_VOICE_NAME = "gpt_sovits"


def _is_clone_voice(voice: str | None) -> bool:
    return bool(voice) and str(voice).startswith(GPT_SOVITS_CLONE_PREFIX)


def build_gpt_sovits_provider(base_url: str | None = None, timeout: float = 30.0) -> GPTSoVITSProvider:
    return GPTSoVITSProvider(base_url=base_url or "http://127.0.0.1:9880", timeout=timeout)


def detect_provider_for_voice(voice: str | None) -> str:
    if _is_clone_voice(voice):
        return GPT_SOVITS_VOICE_NAME
    return EDGE_VOICE_NAME


# ===== P7-1 MiniMax TTS HTTP adapter (cloud API) =====
from .minimax_tts import MiniMaxTTSProvider, MiniMaxTTSError  # noqa: F401

MINIMAX_CLONE_PREFIX = "minimax-clone:"
MINIMAX_VOICE_NAME = "minimax"


def _is_minimax_clone_voice(voice: str | None) -> bool:
    return bool(voice) and (
        str(voice).startswith(MINIMAX_CLONE_PREFIX)
        or str(voice).startswith("minimax_clone:")
    )


def build_minimax_provider(api_key: str | None = None, model: str = "speech-02-turbo",
                            timeout: float = 30.0) -> MiniMaxTTSProvider:
    return MiniMaxTTSProvider(api_key=api_key, model=model, timeout=timeout)


# 扩展现有 detect_provider_for_voice
_original_detect = detect_provider_for_voice


def detect_provider_for_voice(voice: str | None) -> str:  # noqa: F811
    if _is_minimax_clone_voice(voice):
        return MINIMAX_VOICE_NAME
    return _original_detect(voice)


# ===== P8-OmniVoice HTTP adapter (fallback = edge_tts) =====
from .omnivoice_tts import (  # noqa: F401
    OmniVoiceTTSProvider,
    OmniVoiceTTSError,
    is_omnivoice_voice as _is_omnivoice_voice,
    build_omnivoice_provider,
)

OMNIVOICE_VOICE_NAME = "omnivoice"

_original_detect_v2 = detect_provider_for_voice

def detect_provider_for_voice(voice):  # noqa: F811
    if _is_omnivoice_voice(voice):
        return OMNIVOICE_VOICE_NAME
    return _original_detect_v2(voice)

# ===== P7-Fallback TTS 兜底链 =====
def synthesize_tts_with_fallback(
    text,
    destination,
    *,
    voice: str | None = None,
    language: str = "zh",
    voice_cache: dict | None = None,
    prefer: str = "auto",
):
    from providers.base import ProviderError  # except 子句陷阱: 必须函数顶部 import
    if not text or not str(text).strip():
        raise ProviderError("synthesize_tts_with_fallback requires non-empty text")

    text = str(text).strip()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    wants_minimax = (
        prefer == "minimax"
        or (prefer == "auto" and bool(voice) and _is_minimax_clone_voice(voice))
    )

    errors: list[str] = []
    if wants_minimax and os.getenv("MINIMAX_API_KEY"):
        voice_id = voice
        if voice:
            for prefix in (MINIMAX_CLONE_PREFIX, "minimax_clone:"):
                if voice.startswith(prefix):
                    voice_id = voice[len(prefix):]
                    break
        try:
            provider = build_minimax_provider()
            if voice_cache:
                provider.load_cache(voice_cache)
            result = provider.synthesize_with_voice_id(
                text, destination, voice_id, language=language
            )
            result["tts_provider"] = MINIMAX_VOICE_NAME
            return result
        except ProviderError as exc:
            errors.append(f"minimax: {exc}")
        except Exception as exc:  # noqa: BLE001 - 兜底链吞非 ProviderError
            errors.append(f"minimax: {exc}")

    # 兜底: edge_tts (清掉 omnivoice / clone 前缀, edge_tts 不认这些)
    edge_voice = DEFAULT_VOICE
    if voice and not _is_minimax_clone_voice(voice) and not _is_omnivoice_voice(voice):
        edge_voice = voice
    if _is_omnivoice_voice(voice) and not wants_minimax:
        try:
            provider = build_omnivoice_provider()
            result = provider.synthesize(text, destination, voice=voice, language=language)
            result["tts_provider"] = OMNIVOICE_VOICE_NAME
            if errors:
                result["fallback_errors"] = errors
            return result
        except ProviderError as exc:
            errors.append(f"omnivoice: {exc}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"omnivoice: {exc}")

    result = EdgeTTSProvider().synthesize(text, destination, voice=edge_voice)
    result["tts_provider"] = EDGE_VOICE_NAME
    if errors:
        result["fallback_errors"] = errors
    return result
