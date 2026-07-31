"""rev24 阶段 D P1-A: /metrics user/tenant 维度合约测试.

锁定 4 个端点的响应 schema, 防止后续重构破坏:
- GET /metrics/summary        全局计数 + 资源
- GET /metrics/users          按 user_id 聚合
- GET /metrics/users/{user_id} 单用户详情
- GET /metrics/tenants        框架占位
"""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

import main
from fastapi import HTTPException


# 复用 test_api_contract.py 的 _check_schema
_spec = importlib.util.spec_from_file_location(
    "_api_contract_helpers",
    Path(__file__).parent / "test_api_contract.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["_api_contract_helpers"] = _mod
_spec.loader.exec_module(_mod)
_check_schema = _mod._check_schema


class _MetricsBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "metrics.db")
        main.init_db()
        # users 表 schema.sql 没建, 在 lifespan 走 ensure_users_table
        from auth_router import ensure_users_table as _eut
        _eut()
        self.routes = {}
        for route in main.app.routes:
            if not hasattr(route, "endpoint"):
                continue
            for method in (getattr(route, "methods", None) or []):
                self.routes[(method, route.path)] = route.endpoint

    def tearDown(self):
        main.config["DB_PATH"] = self.original_db_path
        self.temp_dir.cleanup()

    def call(self, method, path, **kwargs):
        endpoint = self.routes.get((method, path))
        if endpoint is None:
            raise AssertionError(f"route not found: {method} {path}")
        try:
            result = endpoint(**kwargs)
            return 200, result
        except HTTPException as exc:
            return exc.status_code, exc.detail


class MetricsGlobalContract(_MetricsBase):
    def test_global_metrics_shape(self):
        status, payload = self.call("GET", "/metrics/summary")
        self.assertEqual(status, 200)
        _check_schema(payload, {
            "ts": "int",
            "disk_free_gb": "float",
            "counts": "object",
            "tenants": "int",
        })
        # counts 字段允许为 None (fail-open) 或数值
        for key in ("users", "workflow_drafts", "workflow_drafts_confirmed",
                    "scene_drafts", "workflow_runs",
                    "workflow_runs_succeeded", "workflow_runs_failed"):
            v = payload["counts"].get(key)
            self.assertIsNotNone(v, f"missing counts.{key}")
            self.assertIsInstance(v, int)


class MetricsPerUserContract(_MetricsBase):
    def test_per_user_empty(self):
        status, payload = self.call("GET", "/metrics/users")
        self.assertEqual(status, 200)
        _check_schema(payload, {"users": "list", "total_users": "int", "anonymous_drafts": "int"})
        self.assertEqual(payload["total_users"], 0)
        self.assertEqual(payload["users"], [])

    def test_per_user_shape_when_present(self):
        conn = main.get_db()
        try:
            # 注入 1 个 user_id + 2 草稿 (1 confirmed) + 1 run (failed)
            conn.execute(
                "INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("u-metrics-1", "m1@example.com", "salt", "hash", "user", 1, 1),
            )
            conn.execute(
                "INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?)",
                ("d-1", "draft1", "src", "zh-CN", "draft", 1, "u-metrics-1"),
            )
            conn.execute(
                "INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at, user_id, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)",
                ("d-2", "draft2", "src", "zh-CN", "confirmed", 1, "u-metrics-1", "2026-01-01"),
            )
            conn.execute(
                "INSERT INTO workflow_runs (id, workflow_draft_id, status, progress, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, 1, 1, ?)",
                ("r-1", "d-1", "failed", 50, "u-metrics-1"),
            )
            conn.commit()
        finally:
            conn.close()
        status, payload = self.call("GET", "/metrics/users")
        self.assertEqual(status, 200)
        self.assertEqual(payload["total_users"], 1)
        self.assertEqual(payload["users"][0]["user_id"], "u-metrics-1")
        self.assertEqual(payload["users"][0]["drafts_total"], 2)
        self.assertEqual(payload["users"][0]["drafts_confirmed"], 1)
        self.assertEqual(payload["users"][0]["runs_total"], 1)
        self.assertEqual(payload["users"][0]["runs_failed"], 1)


class MetricsUserDetailContract(_MetricsBase):
    def test_user_detail_404(self):
        status, payload = self.call("GET", "/metrics/users/{user_id}", user_id="nobody")
        self.assertEqual(status, 404)

    def test_user_detail_shape(self):
        conn = main.get_db()
        try:
            conn.execute(
                "INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("u-detail-1", "d1@example.com", "salt", "hash", "user", 1, 1),
            )
            conn.execute(
                "INSERT INTO workflow_drafts (id, title, source_script, language, status, version, created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?)",
                ("d-detail-1", "D", "src", "zh-CN", "draft", 1, "u-detail-1"),
            )
            conn.commit()
        finally:
            conn.close()
        status, payload = self.call("GET", "/metrics/users/{user_id}", user_id="u-detail-1")
        self.assertEqual(status, 200)
        _check_schema(payload, {"user_id": "string", "drafts": "list", "runs": "list"})
        self.assertEqual(payload["user_id"], "u-detail-1")
        self.assertEqual(len(payload["drafts"]), 1)
        self.assertEqual(payload["drafts"][0]["id"], "d-detail-1")


class MetricsTenantsContract(_MetricsBase):
    def test_tenants_shape(self):
        status, payload = self.call("GET", "/metrics/tenants")
        self.assertEqual(status, 200)
        _check_schema(payload, {"tenants": "list", "total": "int", "note": "string"})
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["tenants"]), 1)
        self.assertEqual(payload["tenants"][0]["tenant_id"], "default")


if __name__ == "__main__":
    unittest.main()
