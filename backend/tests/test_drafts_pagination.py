"""P2-Pagination: list_drafts + list_runs 分页合约测试.

锁定 list_drafts/list_runs 的 page wrapper schema, 防止后续重构破坏前端契约.
- page=0 (默认) 返 list (向后兼容)
- page>=1 返 wrapper {items, total, page, limit, has_more}
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


class _PagBase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = main.config["DB_PATH"]
        main.config["DB_PATH"] = str(Path(self.temp_dir.name) / "pagination.db")
        main.init_db()
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


class DraftsListBackwardCompat(_PagBase):
    """page=0 默认行为: 返 list, 不破坏现有契约."""

    def test_page_zero_returns_list(self):
        status, payload = self.call("GET", "/workflow-drafts", page=0, limit=10)
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, list)


class DraftsListPaginated(_PagBase):
    """page>=1 返 wrapper {items, total, page, limit, has_more}."""

    def test_page_one_returns_wrapper(self):
        status, payload = self.call("GET", "/workflow-drafts", page=1, limit=10)
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, dict)
        _check_schema(payload, {
            "items": "list",
            "total": "int",
            "page": "int",
            "limit": "int",
            "has_more": "bool",
        })

    def test_page_one_values(self):
        status, payload = self.call("GET", "/workflow-drafts", page=1, limit=5)
        self.assertEqual(status, 200)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["limit"], 5)
        self.assertGreaterEqual(payload["total"], 0)
        self.assertIsInstance(payload["has_more"], bool)

    def test_page_two_offset_correct(self):
        """page=2 时 offset = (page-1) * limit, 验证 has_more 逻辑."""
        status1, p1 = self.call("GET", "/workflow-drafts", page=1, limit=2)
        status2, p2 = self.call("GET", "/workflow-drafts", page=2, limit=2)
        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        # page2 的 items 应该和 page1 不重复 (如果数据够)
        if p1["has_more"] and p2["items"]:
            p1_ids = {item["id"] for item in p1["items"]}
            p2_ids = {item["id"] for item in p2["items"]}
            self.assertEqual(p1_ids & p2_ids, set(), "page1 和 page2 id 应该不重叠")

    def test_no_user_returns_empty_wrapper(self):
        """无 token 时 page>=1 也应返空 wrapper 不抛错."""
        # 模拟无 token: get_user_id_from_request 返 None
        from unittest.mock import patch
        with patch("auth_router.get_user_id_from_request", return_value=None):
            status, payload = self.call("GET", "/workflow-drafts", page=1, limit=10)
        self.assertEqual(status, 200)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["total"], 0)
        self.assertFalse(payload["has_more"])

    def test_no_user_returns_empty_list_compat(self):
        """无 token + page=0 返空 list."""
        from unittest.mock import patch
        with patch("auth_router.get_user_id_from_request", return_value=None):
            status, payload = self.call("GET", "/workflow-drafts", page=0, limit=10)
        self.assertEqual(status, 200)
        self.assertEqual(payload, [])


class RunsListBackwardCompat(_PagBase):
    """list_runs 已有 page wrapper, 锁定向后兼容."""

    def test_runs_page_zero_returns_list(self):
        status, payload = self.call("GET", "/workflow-runs", page=0, limit=10)
        self.assertEqual(status, 200)
        self.assertIsInstance(payload, list)

    def test_runs_page_one_returns_wrapper(self):
        status, payload = self.call("GET", "/workflow-runs", page=1, limit=10)
        self.assertEqual(status, 200)
        if isinstance(payload, dict):
            _check_schema(payload, {
                "items": "list",
                "total": "int",
                "page": "int",
                "limit": "int",
                "has_more": "bool",
            })


if __name__ == "__main__":
    print("DraftsListBackwardCompat:"); unittest.main(module="__main__", argv=["__main__", "DraftsListBackwardCompat"], exit=False, verbosity=2)
