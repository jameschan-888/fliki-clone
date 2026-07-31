import os
import unittest
from unittest import mock

import env_check


class GPTSoVITSHealthcheckTest(unittest.TestCase):
    def test_offline_returns_available_false(self):
        with mock.patch.dict(os.environ, {"FLIKI_GPT_SOVITS_URL": "http://127.0.0.1:1"}, clear=False):
            with mock.patch("httpx.get", side_effect=Exception("connection refused")):
                info = env_check.check_gpt_sovits()
        self.assertFalse(info["available"])
        self.assertIn("connection refused", info["error"] or "")
        self.assertEqual(info["http_status"], None)

    def test_5xx_marks_unavailable(self):
        class _Resp:
            status_code = 502
        with mock.patch("httpx.get", return_value=_Resp()):
            info = env_check.check_gpt_sovits()
        self.assertFalse(info["available"])
        self.assertEqual(info["http_status"], 502)

    def test_4xx_still_treated_as_available(self):
        class _Resp:
            status_code = 404
        with mock.patch("httpx.get", return_value=_Resp()):
            info = env_check.check_gpt_sovits()
        self.assertTrue(info["available"])
        self.assertEqual(info["http_status"], 404)

    def test_configured_url_overrides_default(self):
        with mock.patch.dict(os.environ, {"FLIKI_GPT_SOVITS_URL": "http://192.168.1.20:9880"}, clear=False):
            class _Resp:
                status_code = 200
            with mock.patch("httpx.get", return_value=_Resp()):
                info = env_check.check_gpt_sovits()
        self.assertEqual(info["configured_url"], "http://192.168.1.20:9880/")
        self.assertTrue(info["available"])


if __name__ == "__main__":
    unittest.main()
