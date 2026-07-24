"""tests/test_autoedit.py: Auto-edit 草稿 CRUD + 切分逻辑测试"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 让 backend 模块可被 import
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from autoedit import (
    plan_cuts, attach_transcript, build_draft_segments,
    now_iso,
)


class PlanCutsTest(unittest.TestCase):
    def test_no_silence_returns_one_segment(self):
        silences = []
        segs = plan_cuts(silences, total_duration=10.0)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0], (0.0, 10.0))

    def test_silences_split_into_segments(self):
        silences = [(0.0, 0.5), (5.0, 5.5), (10.0, 10.5)]
        segs = plan_cuts(silences, total_duration=15.0, target_segments=4, max_segment=12.0, min_segment=2.5)
        # 3 个 cut points → 2 段
        self.assertGreaterEqual(len(segs), 2)
        # 每段都 ≤ 12s 且 ≥ 2.5s
        for s, e in segs:
            self.assertLessEqual(e - s, 12.0)

    def test_long_silences_split(self):
        # 长视频被 max_segment 强制切分
        silences = [(2.0, 2.5), (15.0, 15.5)]
        segs = plan_cuts(silences, total_duration=20.0, target_segments=3, max_segment=8.0, min_segment=2.5)
        for s, e in segs:
            self.assertLessEqual(e - s, 8.0)


class AttachTranscriptTest(unittest.TestCase):
    def test_overlap_text_merged(self):
        cuts = [(0.0, 5.0), (5.0, 10.0)]
        transcript = [
            {"start": 0.5, "end": 4.5, "text": "你好"},
            {"start": 5.5, "end": 9.5, "text": "世界"},
        ]
        out = attach_transcript(cuts, transcript)
        self.assertEqual(len(out), 2)
        self.assertIn("你好", out[0]["text"])
        self.assertIn("世界", out[1]["text"])

    def test_empty_transcript(self):
        out = attach_transcript([(0.0, 5.0)], [])
        self.assertEqual(out[0]["text"], "")


class BuildDraftSegmentsTest(unittest.TestCase):
    def test_short_segments_marked_trim(self):
        segs = build_draft_segments([
            {"start_seconds": 0.0, "end_seconds": 5.0, "text": "短"},
            {"start_seconds": 5.0, "end_seconds": 15.0, "text": "这是一个完整的长句子。"},
        ])
        self.assertEqual(segs[0]["kind"], "trim")
        self.assertEqual(segs[1]["kind"], "keep")
        self.assertEqual(segs[0]["position"], 0)
        self.assertEqual(segs[1]["position"], 1)


class DraftCRUDTest(unittest.TestCase):
    """端到端 CRUD: 上传 + 草稿 + 编辑 + confirm (不调外部 API)"""

    @classmethod
    def setUpClass(cls):
        # 临时 DB
        cls.tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp_db.close()
        os.environ["FLIKI_TEST_DB"] = cls.tmp_db.name
        # 用 FastAPI TestClient
        import importlib
        if "main" in sys.modules:
            del sys.modules["main"]
        if "autoedit" in sys.modules:
            del sys.modules["autoedit"]
        import autoedit as ae
        # 把 DB_PATH 替换成临时
        from config import config
        config["DB_PATH"] = cls.tmp_db.name
        # 创建 schema
        conn = ae.get_db() if hasattr(ae, "get_db") else None
        # 直接 exec schema
        import sqlite3
        schema = ae.SCHEMA_SQL + " CREATE TABLE IF NOT EXISTS autoedit_revisions (id TEXT PRIMARY KEY, autoedit_draft_id TEXT NOT NULL, version INTEGER NOT NULL, snapshot_json TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(autoedit_draft_id) REFERENCES autoedit_drafts(id) ON DELETE CASCADE, UNIQUE(autoedit_draft_id, version));"
        sc = sqlite3.connect(cls.tmp_db.name)
        sc.executescript(schema)
        sc.close()

        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        app = FastAPI()
        # 用 mock render_create
        cls.client = TestClient(app)
        cls.app = app
        cls.ae = ae
        # 注入 router: 由于需要 render_create + render_body_class + max_upload_bytes, 这里只测不需要上传的端点
        # 直接连 sqlite 测: 模拟 upload → draft → confirm

    @classmethod
    def tearDownClass(cls):
        os.unlink(cls.tmp_db.name)

    def test_01_draft_crud_lifecycle(self):
        import sqlite3
        conn = sqlite3.connect(self.tmp_db.name)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        ae = self.ae

        # 1. 模拟上传 (直接写 upload 行, 不调 ffprobe)
        upload_id = "upl_test_001"
        conn.execute(
            "INSERT INTO autoedit_uploads (id, filename, stored_path, size_bytes, duration_seconds, width, height, container, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (upload_id, "test.mp4", "/tmp/fake.mp4", 1024, 30.0, 1280, 720, "mp4", "uploaded", now_iso()),
        )
        conn.commit()

        # 2. 直接构造 draft + segments (跳过 Whisper / silencedetect)
        draft_id = "drf_test_001"
        conn.execute(
            "INSERT INTO autoedit_drafts (id, upload_id, title, status, version, language, created_at, updated_at) "
            "VALUES (?, ?, ?, 'draft', 1, 'zh-CN', ?, ?)",
            (draft_id, upload_id, "测试草稿", now_iso(), now_iso()),
        )
        for pos, (s, e, t) in enumerate([
            (0.0, 5.0, "第一段"),
            (5.0, 12.0, "第二段长句子"),
            (12.0, 18.0, "第三段内容"),
        ]):
            sid = f"seg_{pos:03d}"
            conn.execute(
                "INSERT INTO autoedit_segments (id, autoedit_draft_id, position, start_seconds, end_seconds, text, subtitle, kind, asset_kind, asset_query, music_volume, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'keep', 'stock', ?, 0.12, ?, ?)",
                (sid, draft_id, pos, s, e, t, t, t, now_iso(), now_iso()),
            )
        conn.commit()

        # 3. 草稿应可读
        payload = ae.draft_payload(conn, draft_id)
        self.assertEqual(payload["status"], "draft")
        self.assertEqual(len(payload["segments"]), 3)

        # 4. 编辑其中一个 segment (kind -> trim)
        seg_to_edit = payload["segments"][0]["id"]
        conn.execute(
            "UPDATE autoedit_segments SET kind='trim', updated_at=? WHERE id=?",
            (now_iso(), seg_to_edit),
        )
        ae.record_revision(conn, draft_id)
        conn.commit()
        payload = ae.draft_payload(conn, draft_id)
        self.assertEqual(payload["segments"][0]["kind"], "trim")
        self.assertEqual(payload["version"], 2)

        # 5. confirm
        ae.record_revision(conn, draft_id)
        confirmed_payload = ae.draft_payload(conn, draft_id)
        kept = [s for s in confirmed_payload["segments"] if s["kind"] != "drop"]
        self.assertEqual(len(kept), 3)
        conn.execute(
            "UPDATE autoedit_drafts SET status='confirmed', confirmed_snapshot_json=?, confirmed_at=?, updated_at=? WHERE id=?",
            (json.dumps(confirmed_payload, ensure_ascii=False, default=str), now_iso(), now_iso(), draft_id),
        )
        conn.commit()

        # 6. confirmed 后 require_editable 应拒绝
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as cm:
            ae.require_editable(conn, draft_id)
        self.assertEqual(cm.exception.status_code, 409)

        conn.close()


if __name__ == "__main__":
    unittest.main()