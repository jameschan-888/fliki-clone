import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from voice_gallery import create_router, replace_voices


SAMPLE_VOICES = [
    {"ShortName": "zh-CN-XiaoxiaoNeural", "Gender": "Female", "Locale": "zh-CN", "FriendlyName": "Microsoft Xiaoxiao - Chinese (Mainland)", "SuggestedCodec": "audio-24khz-48kbitrate-mono-mp3", "Status": "GA", "VoiceType": "Neural"},
    {"ShortName": "zh-CN-YunxiNeural", "Gender": "Male", "Locale": "zh-CN", "FriendlyName": "Microsoft Yunxi - Chinese (Mainland)", "SuggestedCodec": "audio-24khz-48kbitrate-mono-mp3", "Status": "GA", "VoiceType": "Neural"},
    {"ShortName": "en-US-JennyNeural", "Gender": "Female", "Locale": "en-US", "FriendlyName": "Microsoft Jenny - English (United States)", "SuggestedCodec": "audio-24khz-48kbitrate-mono-mp3", "Status": "GA", "VoiceType": "Neural"},
]


class FakeCommunicate:
    def __init__(self, text, voice):
        self.text = text
        self.voice = voice

    async def save(self, destination):
        Path(destination).write_bytes(b"ID3" + b"preview-audio" * 100)


class VoiceGalleryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "voices.db"
        self.preview_dir = Path(self.temp_dir.name) / "previews"
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            "CREATE TABLE edge_voices (ShortName TEXT PRIMARY KEY, Gender TEXT, Locale TEXT, "
            "FriendlyName TEXT, SuggestedCodec TEXT, Status TEXT, VoiceType TEXT, fetched_at INTEGER NOT NULL)"
        )
        replace_voices(connection, SAMPLE_VOICES)
        connection.close()

        def get_db():
            database = sqlite3.connect(self.db_path)
            database.row_factory = sqlite3.Row
            return database

        app = FastAPI()
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        app.mount("/voice-previews", StaticFiles(directory=str(self.preview_dir)), name="voice-previews")
        app.include_router(create_router(get_db, self.preview_dir))
        self.client = TestClient(app)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_list_filters_locale_and_gender(self):
        response = self.client.get("/voices", params={"locale": "zh-CN", "gender": "Female"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([voice["ShortName"] for voice in response.json()], ["zh-CN-XiaoxiaoNeural"])

    def test_list_searches_friendly_name(self):
        response = self.client.get("/voices", params={"search": "Jenny"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["Locale"], "en-US")

    def test_locales_returns_grouped_counts(self):
        response = self.client.get("/voices/locales")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"locale": "en-US", "count": 1}, {"locale": "zh-CN", "count": 2}])

    def test_preview_generates_mp3_larger_than_one_kilobyte(self):
        with patch("voice_gallery.edge_tts.Communicate", FakeCommunicate):
            response = self.client.get("/voices/zh-CN-XiaoxiaoNeural/preview", params={"text": "你好世界"})
        self.assertEqual(response.status_code, 200)
        audio_path = self.preview_dir / "zh-CN-XiaoxiaoNeural.mp3"
        self.assertTrue(audio_path.exists())
        self.assertGreater(audio_path.stat().st_size, 1024)
        self.assertEqual(response.json()["audio_url"], "/voice-previews/zh-CN-XiaoxiaoNeural.mp3")

    def test_refresh_fetches_at_least_two_hundred_voices(self):
        fetched = [
            {**SAMPLE_VOICES[0], "ShortName": f"zh-CN-Test{index:03d}Neural", "FriendlyName": f"Test Voice {index}"}
            for index in range(205)
        ]
        with patch("voice_gallery.fetch_edge_voices", AsyncMock(return_value=fetched)):
            response = self.client.post("/voices/refresh")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["count"], 200)
        connection = sqlite3.connect(self.db_path)
        count = connection.execute("SELECT COUNT(*) FROM edge_voices").fetchone()[0]
        connection.close()
        self.assertGreaterEqual(count, 200)


if __name__ == "__main__":
    unittest.main()
