"""P2#11: chat.py POST /chat/apply end-to-end via TestClient.
Covers 5 op (shorten_subtitles / set_aspect / shorten_duration / set_voice / adjust_visual)
via regex default; 1 op via DeepSeek LLM (CHAT_LLM_ENABLED=true); auth (401/404);
validation (422). Real draft created via POST /workflow-drafts to seed scenes."""

import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.pop("CHAT_LLM_ENABLED", None)

import sys
sys.path.insert(0, "backend")
from fastapi.testclient import TestClient

from main import app
from auth_router import _LOGIN_LIMITER, _REGISTER_LIMITER
from db.connection import get_db

SAMPLE_SCRIPT = "第一段介绍产品。第二段说明场景草稿。第三段强调确认后才渲染。第四段展望发布效果。" * 3


class ChatApplyE2EBase(unittest.TestCase):
    "Helper: register a user, login, create draft with scenes, return (client, token, draft_id)."

    def setUp(self):
        _LOGIN_LIMITER.reset()
        _REGISTER_LIMITER.reset()
        self.client = TestClient(app)
        import uuid
        self.email = "chat-e2e-" + uuid.uuid4().hex[:8] + "@e.com"
        self.password = "TestPass123!"
        # register
        r = self.client.post("/auth/register", json={"email": self.email, "password": self.password, "role": "user"})
        self.assertEqual(r.status_code, 200, r.text)
        self.token = r.json()["token"]
        self.user_id = r.json()["user"]["id"]
        self.headers = {"Authorization": "Bearer " + self.token}
        # create draft (no AI -> split_script)
        r = self.client.post("/workflow-drafts", headers=self.headers, json={
            "source_script": SAMPLE_SCRIPT,
            "title": "Chat E2E Test",
            "language": "zh-CN",
        })
        self.assertEqual(r.status_code, 200, r.text)
        self.draft_id = r.json()["id"]
        self.assertGreater(len(r.json()["scenes"]), 0)

    def _get_scenes(self):
        "Fetch scene_drafts for the test draft via raw SQL."
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM scene_drafts WHERE workflow_draft_id=? ORDER BY position", (self.draft_id,)).fetchall()
        return [dict(r) for r in rows]

    def _apply(self, instruction):
        return self.client.post("/chat/apply", headers=self.headers, json={"draft_id": self.draft_id, "instruction": instruction})


class ShortenSubtitlesE2ETest(ChatApplyE2EBase):
    def test_shortens_all_scene_subtitles(self):
        scenes_before = self._get_scenes()
        r = self._apply("shorten subtitles to 30")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["operation"], "shorten_subtitles")
        self.assertEqual(data["params"], {"limit": 30})
        # at least one scene was modified (those whose original subtitle > 30 chars)
        self.assertGreater(data["applied_count"], 0)
        # verify all modified subtitles <= 30
        scenes_after = self._get_scenes()
        for s in scenes_after:
            self.assertLessEqual(len(s["subtitle_display"] or ""), 30)
        # applied list contains before/after
        for entry in data["applied"]:
            self.assertEqual(entry["field"], "subtitle_display")
            self.assertEqual(len(entry["after"]), 30)


class SetAspectE2ETest(ChatApplyE2EBase):
    def test_changes_all_scene_aspect(self):
        r = self._apply("make all 9:16")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["operation"], "set_aspect")
        self.assertEqual(data["params"]["aspect"], "9:16")
        self.assertGreater(data["applied_count"], 0)
        scenes_after = self._get_scenes()
        for s in scenes_after:
            self.assertEqual(s["video_aspect"], "9:16")


class ShortenDurationE2ETest(ChatApplyE2EBase):
    def test_shortens_each_scene_duration(self):
        scenes_before = self._get_scenes()
        before_total = sum(s["duration_seconds"] or 0 for s in scenes_before)
        r = self._apply("shorten scenes by 0.5s")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["operation"], "shorten_duration")
        self.assertEqual(data["params"], {"seconds": 0.5})
        scenes_after = self._get_scenes()
        for s in scenes_after:
            old = next(b["duration_seconds"] for b in scenes_before if b["id"] == s["id"])
            self.assertAlmostEqual(s["duration_seconds"], max(0.5, round(old - 0.5, 1)), places=1)


class SetVoiceE2ETest(ChatApplyE2EBase):
    def test_changes_all_scene_voice(self):
        r = self._apply("voice to zh-CN-YunxiNeural")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["operation"], "set_voice")
        self.assertEqual(data["params"]["voice"], "zh-CN-YunxiNeural")
        self.assertGreater(data["applied_count"], 0)
        scenes_after = self._get_scenes()
        for s in scenes_after:
            self.assertEqual(s["voice"], "zh-CN-YunxiNeural")


class AdjustVisualE2ETest(ChatApplyE2EBase):
    def test_appends_keyword_to_visual_intent(self):
        scenes_before = self._get_scenes()
        r = self._apply("add sunset to visual")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["operation"], "adjust_visual")
        self.assertEqual(data["params"]["keyword"], "sunset")
        scenes_after = self._get_scenes()
        for s_before, s_after in zip(scenes_before, scenes_after):
            self.assertIn("sunset", s_after["visual_intent"])
            # before keyword was not in scene
            self.assertNotIn("sunset", s_before["visual_intent"])

    def test_darken_shortcut_sets_dark_moody(self):
        r = self._apply("darken everything")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["operation"], "adjust_visual")
        self.assertEqual(r.json()["params"]["keyword"], "dark moody")

    def test_brighten_shortcut(self):
        r = self._apply("brighten")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["params"]["keyword"], "bright vibrant")


class AuthAndValidationE2ETest(ChatApplyE2EBase):
    def test_unauthenticated_401(self):
        r = self.client.post("/chat/apply", json={"draft_id": self.draft_id, "instruction": "shorten subtitles to 10"})
        self.assertEqual(r.status_code, 401)

    def test_unknown_draft_404(self):
        r = self.client.post("/chat/apply", headers=self.headers, json={"draft_id": "deadbeef-not-exist", "instruction": "shorten subtitles to 10"})
        self.assertEqual(r.status_code, 404)

    def test_cross_user_404(self):
        "Register second user, try to apply on first user's draft -> 404."
        import uuid
        email2 = "chat-e2e-b-" + uuid.uuid4().hex[:8] + "@e.com"
        r = self.client.post("/auth/register", json={"email": email2, "password": self.password, "role": "user"})
        self.assertEqual(r.status_code, 200, r.text)
        token2 = r.json()["token"]
        headers2 = {"Authorization": "Bearer " + token2}
        r = self.client.post("/chat/apply", headers=headers2, json={"draft_id": self.draft_id, "instruction": "shorten subtitles to 10"})
        self.assertEqual(r.status_code, 404)

    def test_missing_fields_422(self):
        r = self.client.post("/chat/apply", headers=self.headers, json={})
        self.assertEqual(r.status_code, 422)
        r = self.client.post("/chat/apply", headers=self.headers, json={"draft_id": self.draft_id})
        self.assertEqual(r.status_code, 422)

    def test_unknown_instruction_422(self):
        r = self._apply("do something random gibberish xyz")
        self.assertEqual(r.status_code, 422)
        body = r.json()
        # D2 error format: {error_code, message, hint, details, status}
        message = body.get("message", "")
        if not message and isinstance(body.get("detail"), dict):
            message = body["detail"].get("message", "")
        self.assertIn("Supported", message)


class ChatLlmE2ETest(ChatApplyE2EBase):
    "LLM mode: mock DeepSeek, verify instruction routed through DeepSeek path."

    def setUp(self):
        super().setUp()
        os.environ["CHAT_LLM_ENABLED"] = "true"

    def tearDown(self):
        os.environ.pop("CHAT_LLM_ENABLED", None)

    def test_deepseek_returns_set_aspect(self):
        content = r'{"op":"set_aspect","params":{"aspect":"1:1"},"confidence":0.95}'
        fake = MagicMock()
        fake.generate = MagicMock(return_value={"content": content, "model": "deepseek-chat", "usage": {}})
        with patch("providers.text.deepseek_text.DeepSeekTextProvider", MagicMock(return_value=fake)):
            r = self._apply("变成方形")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["operation"], "set_aspect")
        self.assertEqual(data["params"]["aspect"], "1:1")
        fake.generate.assert_called_once()

    def test_llm_fails_falls_back_to_regex(self):
        "DeepSeek raises -> regex path picks up English instruction."
        fake = MagicMock()
        fake.generate = MagicMock(side_effect=RuntimeError("api down"))
        with patch("providers.text.deepseek_text.DeepSeekTextProvider", MagicMock(return_value=fake)):
            r = self._apply("voice to en-US-AriaNeural")
        # regex matches voice to -> 200
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["operation"], "set_voice")
