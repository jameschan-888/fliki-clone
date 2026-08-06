"""R24 (rev43): /metrics user/tenant 维度测试 - TestClient 收口, 不依赖 5181 端口.

原 rev24 rev24 阶段 D P1-A: /metrics 加 user/tenant 维度.
改写原因: 原版用 urllib.request.urlopen(http://127.0.0.1:5181/...) 要求 5181 端口后端在跑, 无后端则 setUpClass SkipTest.
改写后: TestClient in-process 调 FastAPI app, 用同一 DB (config[DB_PATH]), 不依赖网络/子进程.

覆盖:
  - /metrics 200 + 含 user_id label 的 metrics
  - fliki_render_jobs_per_user_total / fliki_workflow_runs_per_user_total / fliki_top_users_by_jobs / fliki_active_users_24h
  - top N cap = 10, 其他用户聚合到 user_id="other"
  - 整体行数 < 250 (防 cardinality 爆炸, 留余量)
  - Prometheus 格式合法 (key/value + tag)
"""
import json, os, re, sqlite3, sys, unittest

# P0#2: conftest.py 已设 FLIKI_ENV=test, 但保险起见显式设一次.
os.environ.setdefault("FLIKI_ENV", "test")
sys.path.insert(0, "backend")

from fastapi.testclient import TestClient

from main import app
from auth_router import _LOGIN_LIMITER, _REGISTER_LIMITER
from db.connection import get_db

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "app.db")


def _register(client, email, password="test12345") -> dict:
    r = client.post("/auth/register", json={"email": email, "password": password, "role": "user"})
    assert r.status_code == 200, r.text
    return r.json()


def _login(client, email, password="test12345") -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    return r.json()


class P1AUserMetricsTests(unittest.TestCase):
    "R24: /metrics user/tenant 维度 via TestClient."

    @classmethod
    def setUpClass(cls):
        _LOGIN_LIMITER.reset()
        _REGISTER_LIMITER.reset()
        cls.client = TestClient(app)
        r = cls.client.get("/metrics")
        assert r.status_code == 200, "/metrics " + str(r.status_code)
        cls.body = r.text

    def test_metrics_has_per_user_labels(self):
        for metric in (
            "fliki_render_jobs_per_user_total",
            "fliki_workflow_runs_per_user_total",
            "fliki_top_users_by_jobs",
            "fliki_active_users_24h",
        ):
            self.assertIn(metric, self.body, "missing user-dim metric " + repr(metric))

    def test_per_user_metrics_have_user_id_label(self):
        pattern = re.compile("fliki_render_jobs_per_user_total\\{user_id=\"([^\"]+)\", status=\"([^\"]+)\"\\} (\\d+)")
        matches = pattern.findall(self.body)
        self.assertGreater(len(matches), 0, "no fliki_render_jobs_per_user_total rows")
        for user_id, status, cnt in matches:
            self.assertTrue(user_id, "user_id label empty")
            self.assertTrue(status, "status label empty")
            self.assertGreater(int(cnt), 0, "count must be > 0, got " + str(cnt))

    def test_top_users_by_jobs_rank_desc(self):
        pattern = re.compile("fliki_top_users_by_jobs\\{user_id=\"([^\"]+)\", rank=\"(\\d+)\"\\} (\\d+)")
        rows = [(u, int(r), int(c)) for u, r, c in pattern.findall(self.body)]
        self.assertGreater(len(rows), 0, "no top_users rows")
        cnts = [c for _, _, c in rows]
        for i in range(1, len(cnts)):
            self.assertGreaterEqual(cnts[i - 1], cnts[i], "top_users not sorted DESC at idx " + str(i) + ": " + str(cnts[i-1]) + " < " + str(cnts[i]))
        ranks = sorted([r for _, r, _ in rows])
        self.assertEqual(ranks, list(range(1, len(rows) + 1)), "rank not contiguous: " + str(ranks))

    def test_top_users_cap_at_10(self):
        pattern = re.compile("fliki_top_users_by_jobs\\{rank=\"(\\d+)\"\\}")
        ranks = [int(r) for r in pattern.findall(self.body)]
        for r in ranks:
            self.assertLessEqual(r, 10, "rank " + str(r) + " > 10 (TOP_N cap broken)")

    def test_active_users_24h_nonneg(self):
        pattern = re.compile("fliki_active_users_24h\\{source=\"([^\"]+)\"\\} (\\d+)")
        rows = pattern.findall(self.body)
        self.assertGreater(len(rows), 0, "no active_users_24h rows")
        for source, cnt in rows:
            self.assertIn(source, ("render_jobs", "workflow_runs"))
            self.assertGreaterEqual(int(cnt), 0, "active_users_24h negative for " + source)

    def test_no_high_cardinality_explosion(self):
        lines = [l for l in self.body.split(chr(10)) if l and not l.startswith("#")]
        self.assertLess(len(lines), 250, "metrics 行数 " + str(len(lines)) + " 超过 250 (cardinality 边界)")

    def test_prometheus_format_valid(self):
        for line in self.body.split(chr(10)):
            if not line or line.startswith("#"):
                continue
            m = re.match("^([a-zA-Z_][a-zA-Z0-9_]*)(\\{[^}]*\\})? (-?\\d+\\.?\\d*)\\s*$", line)
            self.assertIsNotNone(m, "malformed prom line: " + repr(line))

    def test_user_id_other_bucket_aggregation(self):
        if not os.path.exists(DB_PATH):
            self.skipTest("no db")
        with get_db() as conn:
            row = conn.execute("SELECT COUNT(DISTINCT user_id) FROM render_jobs WHERE user_id IS NOT NULL").fetchone()
        distinct_users = row[0] if row else 0
        top_pattern = re.compile("fliki_top_users_by_jobs\\{user_id=\"([^\"]+)\"")
        top_users = set(top_pattern.findall(self.body))
        if distinct_users <= 10:
            self.assertNotIn("other", top_users, "other bucket should not appear when distinct_users <= 10")
            self.assertEqual(len(top_users), distinct_users, "top_users=" + str(len(top_users)) + " but DB distinct=" + str(distinct_users))
        else:
            self.assertIn("user_id=\"other\"", self.body, "per_user_total 必须含 other 桶 (distinct_users > 10)")


if __name__ == "__main__":
    unittest.main()
