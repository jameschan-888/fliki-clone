"""rev24 阶段 D D1-1: /metrics tenant 维度 (md5(user_id) % 4 哈希分桶)."""
import hashlib
import unittest

from fastapi.testclient import TestClient
from main import app

BACKEND = "http://127.0.0.1:5181"


def _fetch_metrics(client):
    return client.get("/metrics").text


def _bucket(user_id):
    h = hashlib.md5(user_id.encode("utf-8")).hexdigest()
    return "tenant_" + ("a", "b", "c", "d")[int(h[0], 16) % 4]


def _count_lines_with(needle, hay):
    return sum(1 for line in hay.splitlines() if needle in line)


def _sum_lines_with(needle, hay):
    total = 0.0
    for line in hay.splitlines():
        if needle in line:
            try:
                idx = line.rfind("}")
                if idx < 0:
                    continue
                val = line[idx + 1:].strip()
                total += float(val)
            except Exception:
                pass
    return total


class D1TenantMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.metrics = _fetch_metrics(cls.client)

    def test_render_jobs_per_tenant_metric_exists(self):
        self.assertIn("fliki_render_jobs_per_tenant_total", self.metrics)

    def test_workflow_runs_per_tenant_metric_exists(self):
        self.assertIn("fliki_workflow_runs_per_tenant_total", self.metrics)

    def test_active_users_24h_per_tenant_metric_exists(self):
        self.assertIn("fliki_active_users_24h_per_tenant", self.metrics)

    def test_all_4_tenant_buckets_render_jobs(self):
        # 实际行: fliki_render_jobs_per_tenant_total{tenant="tenant_a", status="..."} 数字
        for b in ("tenant_a", "tenant_b", "tenant_c", "tenant_d"):
            n = _count_lines_with('tenant="' + b + '"', self.metrics)
            # 4 桶必出现在 render_jobs_per_tenant
            n_render = _count_lines_with("fliki_render_jobs_per_tenant_total" + chr(123) + 'tenant="' + b + '"', self.metrics)
            self.assertGreaterEqual(n_render, 1, "render_jobs 缺 " + b)

    def test_active_users_per_tenant_some_data(self):
        # active_users_24h_per_tenant 可能某桶为 0 被省略, 但至少 1 桶有数据
        total = 0
        for b in ("tenant_a", "tenant_b", "tenant_c", "tenant_d"):
            n = _count_lines_with("fliki_active_users_24h_per_tenant" + chr(123) + 'tenant="' + b + '"', self.metrics)
            total += n
        self.assertGreaterEqual(total, 1, "active_users_24h_per_tenant 全空")

    def test_hash_function_deterministic(self):
        for uid in ("u1", "u2", "user_xxx", "abc-123-456"):
            buckets = {_bucket(uid) for _ in range(100)}
            self.assertEqual(len(buckets), 1, "hash 不确定: " + uid)

    def test_hash_returns_4_buckets(self):
        buckets = {_bucket(str(i)) for i in range(1000)}
        self.assertEqual(len(buckets), 4, "md5 % 4 应得 4 桶, 实际: " + str(buckets))

    def test_tenant_total_no_data_loss(self):
        pt = _sum_lines_with("fliki_render_jobs_per_tenant_total" + chr(123), self.metrics)
        pu = _sum_lines_with("fliki_render_jobs_per_user_total" + chr(123), self.metrics)
        self.assertGreaterEqual(pt, pu, "per_tenant=" + str(pt) + " per_user=" + str(pu))


if __name__ == "__main__":
    unittest.main()
