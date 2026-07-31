"""P8: highlight_scorer 单元 + 集成测试."""
import sys
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from highlight_scorer import (
    HighlightScorer,
    MockHighlightLLM,
    OpenAICompatibleLLM,
    ensure_highlight_columns,
    score_draft,
    HIGHLIGHT_PROMPT,
)


def test_mock_llm_basic():
    """MockLLM 应该给出非零分数, 短/差内容低分, 长/好内容高分."""
    mock = MockHighlightLLM()
    segs = [
        {"id": "good", "subtitle": "数据显示,2026 年 AI 市场规模突破 5000 亿,「算力」是核心", "start_seconds": 30, "end_seconds": 60},
        {"id": "bad", "subtitle": "嗯", "start_seconds": 0, "end_seconds": 1},
    ]
    raw = mock.chat(HIGHLIGHT_PROMPT, segs)
    import json
    parsed = json.loads(raw)
    assert len(parsed) == 2, f"expected 2 results, got {len(parsed)}"
    by_id = {p["id"]: p for p in parsed}
    assert by_id["good"]["highlight_score"] > by_id["bad"]["highlight_score"], \
        f"good ({by_id['good']['highlight_score']}) should > bad ({by_id['bad']['highlight_score']})"
    assert 0 <= by_id["good"]["highlight_score"] <= 1
    assert 0 <= by_id["bad"]["highlight_score"] <= 1
    assert len(by_id["good"]["highlight_reason"]) > 0
    print(f"  good={by_id['good']['highlight_score']:.2f}  bad={by_id['bad']['highlight_score']:.2f}")


def test_highlight_scorer_batch():
    """Scorer 自动按 batch_size 分批, 保持 id 顺序."""
    mock = MockHighlightLLM()
    scorer = HighlightScorer(llm=mock, batch_size=2)
    segs = [{"id": f"s{i}", "subtitle": f"片段{i} 内容", "start_seconds": 0, "end_seconds": 10} for i in range(5)]
    scores = scorer.score_segments(segs)
    assert len(scores) == 5
    ids = [s.segment_id for s in scores]
    assert ids == [f"s{i}" for i in range(5)], f"id order broken: {ids}"
    for s in scores:
        assert 0 <= s.score <= 1
        assert s.reason
    print(f"  batched 5 segments: {ids}")


def test_highlight_scorer_parse_fallback():
    """LLM 返回非 JSON 时应该走 Mock 兜底, 不抛错."""
    class BrokenLLM:
        def chat(self, prompt, input_data):
            return "this is not json"
    scorer = HighlightScorer(llm=BrokenLLM())
    segs = [{"id": "x", "subtitle": "测试", "start_seconds": 0, "end_seconds": 10}]
    scores = scorer.score_segments(segs)
    assert len(scores) == 1
    assert scores[0].segment_id == "x"
    print(f"  fallback works: score={scores[0].score}")


def test_highlight_scorer_codeblock_strip():
    """LLM 输出 ```json ... ``` 应该正确解析."""
    class CodeBlockLLM:
        def chat(self, prompt, input_data):
            return "```json\n[{\"id\": \"x\", \"highlight_score\": 0.9, \"highlight_reason\": \"好\"}]\n```"
    scorer = HighlightScorer(llm=CodeBlockLLM())
    scores = scorer.score_segments([{"id": "x", "subtitle": "测试", "start_seconds": 0, "end_seconds": 10}])
    assert scores[0].score == 0.9
    assert scores[0].reason == "好"
    print(f"  codeblock parse: score={scores[0].score}")


def test_db_migration_idempotent():
    """ensure_highlight_columns 应该幂等, 老 DB + 新 DB 都能跑."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE autoedit_segments (
                id TEXT PRIMARY KEY,
                autoedit_draft_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                start_seconds REAL NOT NULL,
                end_seconds REAL NOT NULL,
                text TEXT NOT NULL,
                subtitle TEXT NOT NULL
            );
        """)
        conn.commit()
        # 老 DB 没有 highlight 列 -> 加
        ensure_highlight_columns(conn)
        cols1 = {row["name"] for row in conn.execute("PRAGMA table_info(autoedit_segments)").fetchall()}
        assert {"highlight_score", "highlight_reason", "highlight_scored_at"}.issubset(cols1)
        # 第二次调 -> 幂等, 不报错
        ensure_highlight_columns(conn)
        cols2 = {row["name"] for row in conn.execute("PRAGMA table_info(autoedit_segments)").fetchall()}
        assert cols1 == cols2
        conn.close()
        print("  migration idempotent: OK")
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_score_draft_writes_back():
    """score_draft 应该读 segments -> 评 -> 写回 highlight_score/reason."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
            CREATE TABLE autoedit_drafts (
                id TEXT PRIMARY KEY,
                upload_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT "draft",
                version INTEGER NOT NULL DEFAULT 1,
                language TEXT NOT NULL DEFAULT "zh-CN",
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE autoedit_segments (
                id TEXT PRIMARY KEY,
                autoedit_draft_id TEXT NOT NULL,
                position INTEGER NOT NULL,
                start_seconds REAL NOT NULL,
                end_seconds REAL NOT NULL,
                text TEXT NOT NULL,
                subtitle TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT "keep",
                asset_kind TEXT, asset_query TEXT, broll_url TEXT,
                music_volume REAL, notes TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
        """)
        conn.execute(
            "INSERT INTO autoedit_drafts (id, upload_id, title, status, version, language, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            ("draft1", "upload1", "test", "draft", 1, "zh-CN", "2026-01-01", "2026-01-01"),
        )
        seg_data = [
            ("seg1", 0, 0, 10, "大家好,今天聊 AI", "大家好,今天聊 AI"),
            ("seg2", 1, 10, 25, "数据显示 2026 年 AI 突破 5000 亿", "数据显示 2026 年 AI 突破 5000 亿,「算力」是核心"),
            ("seg3", 2, 25, 35, "谢谢观看", "谢谢观看"),
        ]
        for sid, pos, s, e, txt, sub in seg_data:
            conn.execute(
                "INSERT INTO autoedit_segments (id, autoedit_draft_id, position, start_seconds, end_seconds, text, subtitle, kind, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (sid, "draft1", pos, s, e, txt, sub, "keep", "2026-01-01", "2026-01-01"),
            )
        conn.commit()
        # 跑评分 (Mock LLM)
        written = score_draft(conn, "draft1", llm=MockHighlightLLM())
        assert written == 3, f"expected 3 writes, got {written}"
        rows = conn.execute("SELECT id, highlight_score, highlight_reason, highlight_scored_at FROM autoedit_segments WHERE autoedit_draft_id=? ORDER BY position", ("draft1",)).fetchall()
        for r in rows:
            assert r["highlight_score"] is not None, f"missing score for {r['id']}"
            assert r["highlight_reason"], f"missing reason for {r['id']}"
            assert r["highlight_scored_at"], f"missing scored_at for {r['id']}"
        # seg2 should score highest (data + quotes)
        seg2_score = [r["highlight_score"] for r in rows if r["id"] == "seg2"][0]
        seg3_score = [r["highlight_score"] for r in rows if r["id"] == "seg3"][0]
        assert seg2_score > seg3_score, f"seg2={seg2_score} should > seg3={seg3_score}"
        print(f"  seg1={[r['highlight_score'] for r in rows if r['id']=='seg1'][0]:.2f}  seg2={seg2_score:.2f}  seg3={seg3_score:.2f}")
        conn.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


if __name__ == "__main__":
    print("test_mock_llm_basic:"); test_mock_llm_basic()
    print("test_highlight_scorer_batch:"); test_highlight_scorer_batch()
    print("test_highlight_scorer_parse_fallback:"); test_highlight_scorer_parse_fallback()
    print("test_highlight_scorer_codeblock_strip:"); test_highlight_scorer_codeblock_strip()
    print("test_db_migration_idempotent:"); test_db_migration_idempotent()
    print("test_score_draft_writes_back:"); test_score_draft_writes_back()
    print("ALL PASS")
