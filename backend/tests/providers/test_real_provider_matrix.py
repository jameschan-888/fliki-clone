"""真实 Provider 联调矩阵.

对 stock (Pexels, Pixabay) 和 music (Freesound) 三个免费 API 做端到端联调:
  - 真实调用 search API
  - 真实下载文件到本地 tmp
  - 用 ffprobe / file 命令校验产出格式 (size, duration, codec)
  - 全部失败时跳过而不是出错 (允许 CI 在无网络时跳过)

依赖: 本机 ffmpeg (ffprobe), 已配置的 FLIKI_PROVIDER_*_API_KEY 在 .env
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
os.chdir(BACKEND_ROOT)
os.environ.setdefault("FLIKI_ENV", "test")

from provider_config import hydrate_env_from_disk  # noqa: E402
hydrate_env_from_disk()

from providers.stock import (  # noqa: E402
    PexelsProvider, PixabayProvider, fetch_with_fallback,
)
from providers.music import FreesoundProvider, fetch_music_with_fallback as music_fallback  # noqa: E402


def _has_ffprobe():
    return shutil.which("ffprobe") is not None


def _ffprobe_meta(path):
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        stderr=subprocess.STDOUT, timeout=30,
    )
    meta = json.loads(out.decode("utf-8"))
    streams = meta.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = meta.get("format", {})
    return {
        "size_bytes": int(fmt.get("size", 0) or 0),
        "duration": float(fmt.get("duration", 0.0) or 0.0),
        "video_codec": video.get("codec_name") if video else None,
        "video_width": int(video.get("width", 0) or 0) if video else 0,
        "video_height": int(video.get("height", 0) or 0) if video else 0,
        "audio_codec": audio.get("codec_name") if audio else None,
    }


class TestPexelsProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = os.environ.get("PEXELS_API_KEY", "")
        cls.skip = not cls.key
        if cls.skip:
            raise unittest.SkipTest("PEXELS_API_KEY not configured; skipping real Pexels test")
        if not _has_ffprobe():
            raise unittest.SkipTest("ffprobe not available")
        cls.tmp = Path(tempfile.mkdtemp(prefix="fliki-pexels-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fetch_landscape_video(self):
        provider = PexelsProvider()
        dest = self.tmp / "pexels.mp4"
        result = provider.fetch("industrial factory aerial", dest)
        self.assertTrue(dest.exists())
        self.assertGreater(dest.stat().st_size, 50_000, "file too small")
        meta = _ffprobe_meta(dest)
        self.assertEqual(meta["video_width"], 1280, f"unexpected width {meta['video_width']}")
        self.assertEqual(meta["video_height"], 720, f"unexpected height {meta['video_height']}")
        self.assertIn(meta["video_codec"], ("h264",))
        print(f"[PEXELS] {meta['size_bytes']/1024:.1f}KB {meta['duration']:.1f}s {meta['video_codec']} {meta['video_width']}x{meta['video_height']}")
        self.assertIn("source_url", result)


class TestPixabayProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = os.environ.get("PIXABAY_API_KEY", "")
        cls.skip = not cls.key
        if cls.skip:
            raise unittest.SkipTest("PIXABAY_API_KEY not configured; skipping real Pixabay test")
        if not _has_ffprobe():
            raise unittest.SkipTest("ffprobe not available")
        cls.tmp = Path(tempfile.mkdtemp(prefix="fliki-pixabay-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fetch_landscape_video(self):
        provider = PixabayProvider()
        dest = self.tmp / "pixabay.mp4"
        result = provider.fetch("city skyline", dest)
        self.assertTrue(dest.exists())
        self.assertGreater(dest.stat().st_size, 50_000)
        meta = _ffprobe_meta(dest)
        self.assertGreater(meta["video_width"], 0)
        self.assertGreater(meta["video_height"], 0)
        self.assertGreater(meta["duration"], 0.5)
        print(f"[PIXABAY] {meta['size_bytes']/1024:.1f}KB {meta['duration']:.1f}s {meta['video_codec']} {meta['video_width']}x{meta['video_height']}")
        self.assertIn("source_url", result)


class TestFreesoundProvider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = os.environ.get("FREESOUND_API_KEY", "")
        cls.skip = not cls.key
        if cls.skip:
            raise unittest.SkipTest("FREESOUND_API_KEY not configured; skipping real Freesound test")
        cls.tmp = Path(tempfile.mkdtemp(prefix="fliki-freesound-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_fetch_background_music(self):
        provider = FreesoundProvider()
        dest = self.tmp / "freesound.mp3"
        result = provider.fetch("ambient background", dest)
        self.assertTrue(dest.exists())
        self.assertGreater(dest.stat().st_size, 50_000)
        # 简单通过 MP3 magic bytes 校验
        with dest.open("rb") as f:
            head = f.read(3)
        self.assertIn(head[:2], (b"ID", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"), f"unexpected MP3 magic {head!r}")
        print(f"[FREESOUND] {dest.stat().st_size/1024:.1f}KB")
        self.assertIn("source_url", result)


class TestStockFallback(unittest.TestCase):
    """fallback 必须能在 Pexels/Pixabay 至少一边成功时返回结果."""

    def test_fetch_with_fallback_returns_first_success(self):
        if not (os.environ.get("PEXELS_API_KEY") or os.environ.get("PIXABAY_API_KEY")):
            raise unittest.SkipTest("no stock provider key configured")
        if not _has_ffprobe():
            raise unittest.SkipTest("ffprobe not available")
        with tempfile.TemporaryDirectory(prefix="fliki-stock-fb-") as tmp:
            dest = Path(tmp) / "fallback.mp4"
            result = fetch_with_fallback("mountain landscape", dest)
            self.assertTrue(dest.exists(), "fallback produced no file")
            self.assertIn(result["provider"], ("pexels", "pixabay"))
            print(f"[STOCK-FB] used={result['provider']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
