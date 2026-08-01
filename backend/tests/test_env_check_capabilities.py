import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import main
from env_check import build_capability_groups


def _row(category, name, enabled=1, is_default=0, priority=0, config_json="{}"):
    return {
        "category": category, "name": name, "enabled": enabled,
        "is_default": is_default, "priority": priority,
        "config_json": config_json,
    }


class BuildCapabilityGroupsTest(unittest.TestCase):
    def test_each_kind_has_providers_and_publish_grade_flag(self):
        rows = [
            _row("tts", "edge_tts", is_default=1, config_json='{"model":"zh-CN-XiaoxiaoNeural"}'),
            _row("tts", "mock", priority=100, config_json='{"is_mock": true}'),
            _row("stock", "pexels", is_default=1, config_json='{"api_key_env":"PEXELS_API_KEY"}'),
            _row("music", "freesound", is_default=1, config_json='{"api_key_env":"FREESOUND_API_KEY"}'),
            _row("music", "silence", priority=100),
            _row("avatar", "wav2lip_onnx", is_default=1, config_json='{"model_path":"x"}'),
        ]
        with tempfile.TemporaryDirectory() as td:
            os.environ["PEXELS_API_KEY"] = "abcd1234wxyz"
            os.environ["FREESOUND_API_KEY"] = "abcd1234wxyz"
            try:
                result = build_capability_groups(
                    rows,
                    ffmpeg_available=True,
                    gpt_sovits_info={"available": True, "latency_ms": 12, "configured_url": "http://x:9880"},
                    wav2lip_info={"ok": True, "latency_ms": 220},
                    capabilities={},
                )
            finally:
                os.environ.pop("PEXELS_API_KEY", None)
                os.environ.pop("FREESOUND_API_KEY", None)
        self.assertIn("groups", result)
        self.assertIn("publish_grade", result)
        kinds = [g["kind"] for g in result["groups"]]
        self.assertEqual(kinds, ["text", "stock", "tts", "music", "avatar"])
        for group in result["groups"]:
            self.assertIn("providers", group)
            self.assertIn("publish_grade", group)
            self.assertIn("default", group)
            for provider in group["providers"]:
                self.assertIn("is_mock", provider)
                self.assertIn("available", provider)
                self.assertIn("is_default", provider)
                self.assertIn("hint", provider)

    def test_mock_default_blocks_publish_grade(self):
        rows = [
            _row("tts", "edge_tts", priority=0),
            _row("tts", "mock", is_default=1, priority=100, config_json='{"is_mock": true}'),
        ]
        result = build_capability_groups(
            rows, ffmpeg_available=True,
            gpt_sovits_info={"available": False, "latency_ms": None},
            wav2lip_info={"ok": False, "latency_ms": None},
            capabilities={},
        )
        tts_group = next(g for g in result["groups"] if g["kind"] == "tts")
        self.assertFalse(tts_group["publish_grade"])
        self.assertEqual(tts_group["default"], "mock")
        mock_provider = next(p for p in tts_group["providers"] if p["name"] == "mock")
        self.assertTrue(mock_provider["is_mock"])

    def test_real_default_with_api_key_passes_publish_grade(self):
        rows = [
            _row("stock", "pexels", is_default=1, config_json='{"api_key_env":"PEXELS_API_KEY"}'),
        ]
        with tempfile.TemporaryDirectory() as td:
            os.environ["PEXELS_API_KEY"] = "abcd1234wxyz"
            try:
                result = build_capability_groups(
                    rows, ffmpeg_available=True,
                    gpt_sovits_info={"available": False, "latency_ms": None},
                    wav2lip_info={"ok": False, "latency_ms": None},
                    capabilities={},
                )
            finally:
                os.environ.pop("PEXELS_API_KEY", None)
        stock_group = next(g for g in result["groups"] if g["kind"] == "stock")
        self.assertTrue(stock_group["publish_grade"])
        self.assertTrue(stock_group["providers"][0]["available"])

    def test_real_default_without_api_key_fails_publish_grade(self):
        rows = [
            _row("stock", "pexels", is_default=1, config_json='{"api_key_env":"PEXELS_API_KEY"}'),
        ]
        os.environ.pop("PEXELS_API_KEY", None)
        result = build_capability_groups(
            rows, ffmpeg_available=True,
            gpt_sovits_info={"available": False, "latency_ms": None},
            wav2lip_info={"ok": False, "latency_ms": None},
            capabilities={},
        )
        stock_group = next(g for g in result["groups"] if g["kind"] == "stock")
        self.assertFalse(stock_group["publish_grade"])
        self.assertFalse(stock_group["providers"][0]["available"])


class EnvCheckIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "app.db")
        main.init_db()
        from provider_config import seed_runtime_providers
        with main.get_db() as conn:
            seed_runtime_providers(conn)
    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        self.temp_dir.cleanup()

    def test_run_full_diagnostic_includes_capability_groups(self):
        from env_check import run_full_diagnostic
        report = run_full_diagnostic()
        self.assertIn("capability_groups", report)
        groups = report["capability_groups"]
        self.assertIn("groups", groups)
        kinds = [g["kind"] for g in groups["groups"]]
        self.assertIn("tts", kinds)
        self.assertIn("avatar", kinds)
        for g in groups["groups"]:
            for provider in g["providers"]:
                self.assertIn("is_mock", provider)
                self.assertIn("available", provider)


if __name__ == "__main__":
    unittest.main()
