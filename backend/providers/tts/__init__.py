import asyncio
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
