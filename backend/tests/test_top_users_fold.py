"""rev39 R11: 直接验证 _top_users_by_activity 折叠行为.

历史债 N55 (踩坑日志): /metrics 行数 200 -> 250 临时阈值, 真修法是聚合 per-user label.
rev24 D 阶段已实现 _top_users_by_activity (top-N=10, 其余 'other' bucket), 但只有端到端
测试在守行为. 本文件用 in-memory sqlite 直接覆盖 helper 的 4 个分支:
  - 空表
  - 无 user_id 列
  - 用户数 < N (全部返回, other=0)
  - 用户数 > N (top N DESC, other = rest 之和)
不依赖 backend 启动 / DB 文件, 纯单元测试.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from routers.analytics import _top_users_by_activity


def _make_con():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    return con


def _seed_render_jobs(con, rows):
    con.execute(
        "CREATE TABLE render_jobs ("
        "user_id TEXT, status TEXT, created_at TEXT)"
    )
    for uid, status, ts in rows:
        con.execute(
            "INSERT INTO render_jobs (user_id, status, created_at) VALUES (?, ?, ?)",
            (uid, status, ts),
        )
    con.commit()


class TopUsersFoldTests(unittest.TestCase):
    """rev39 R11: 折叠 helper 4 分支覆盖."""

    def test_empty_table_returns_empty(self):
        con = _make_con()
        con.execute("CREATE TABLE render_jobs (user_id TEXT, status TEXT)")
        try:
            top, other = _top_users_by_activity(con, "render_jobs", n=10)
            self.assertEqual(top, [])
            self.assertEqual(other, 0)
        finally:
            con.close()

    def test_table_without_user_id_column_returns_empty(self):
        con = _make_con()
        con.execute("CREATE TABLE render_jobs (id INTEGER, status TEXT)")
        con.execute("INSERT INTO render_jobs VALUES (1, 'ok')")
        con.commit()
        try:
            top, other = _top_users_by_activity(con, "render_jobs", n=10)
            self.assertEqual(top, [])
            self.assertEqual(other, 0)
        finally:
            con.close()

    def test_fewer_than_n_users_returns_all_no_other(self):
        con = _make_con()
        _seed_render_jobs(con, [
            ("u1", "ok", "2026-08-01"),
            ("u2", "ok", "2026-08-01"),
            ("u3", "ok", "2026-08-01"),
        ])
        try:
            top, other = _top_users_by_activity(con, "render_jobs", n=10)
            self.assertEqual(len(top), 3)
            self.assertEqual(other, 0)
            user_ids = [u for u, _ in top]
            self.assertEqual(set(user_ids), {"u1", "u2", "u3"})
        finally:
            con.close()

    def test_more_than_n_users_folds_into_other(self):
        con = _make_con()
        # 12 distinct users; u11 gets 3 rows, u10 gets 2, rest get 1
        rows = [(f"u{i}", "ok", "2026-08-01") for i in range(12)]
        rows.append(("u10", "ok", "2026-08-02"))
        rows.append(("u11", "ok", "2026-08-02"))
        rows.append(("u11", "ok", "2026-08-03"))
        _seed_render_jobs(con, rows)
        try:
            top, other = _top_users_by_activity(con, "render_jobs", n=10)
            self.assertEqual(len(top), 10)
            cnts = [c for _, c in top]
            for i in range(1, len(cnts)):
                self.assertGreaterEqual(
                    cnts[i - 1], cnts[i],
                    f"top not DESC at idx {i}: {cnts[i - 1]} < {cnts[i]}",
                )
            # u11 (3) + u10 (2) are top 2; remaining u8, u9 each have 1 = 2 folded
            self.assertEqual(other, 2)
        finally:
            con.close()

    def test_null_user_ids_excluded_from_top(self):
        con = _make_con()
        _seed_render_jobs(con, [
            ("u1", "ok", "2026-08-01"),
            ("u1", "ok", "2026-08-01"),
            (None, "ok", "2026-08-01"),
            (None, "ok", "2026-08-01"),
        ])
        try:
            top, other = _top_users_by_activity(con, "render_jobs", n=10)
            user_ids = [u for u, _ in top]
            self.assertNotIn(None, user_ids)
            self.assertEqual(top, [("u1", 2)])
            self.assertEqual(other, 0)
        finally:
            con.close()


if __name__ == "__main__":
    unittest.main()
