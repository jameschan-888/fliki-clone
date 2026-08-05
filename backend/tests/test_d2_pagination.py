"""rev24 阶段 D D2-2: render_jobs / workflow_runs 分页 API 验证."""
import json

from fastapi.testclient import TestClient
from main import app
import unittest



def _fetch(path):
    response = TestClient(app).get(path)
    return response.status_code, response.text


class RenderJobsPaginationTests(unittest.TestCase):
    def test_page_zero_returns_list(self):
        """?page=0 必须返 list 形态 (向后兼容前端)."""
        status, body = _fetch("/render-jobs?page=0&limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, list, "page=0 必须返 list, 当前: " + type(data).__name__)

    def test_page_one_returns_wrapper(self):
        """?page>=1 必须返 {items, total, page, limit, has_more} wrapper."""
        status, body = _fetch("/render-jobs?page=1&limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict, "page>=1 必须返 dict, 当前: " + type(data).__name__)
        for key in ("items", "total", "page", "limit", "has_more"):
            self.assertIn(key, data, "wrapper 缺 key: " + key)
        self.assertIsInstance(data["items"], list)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["limit"], 5)
        self.assertIsInstance(data["has_more"], bool)
        self.assertIsInstance(data["total"], int)

    def test_total_correct(self):
        """total 数字是当前匿名请求可见的 render_jobs 行数(无 status 过滤)."""
        status1, body1 = _fetch("/render-jobs?page=1&limit=1")
        status2, body2 = _fetch("/render-jobs?page=2&limit=1")
        self.assertEqual(status1, 200)
        self.assertEqual(status2, 200)
        d1 = json.loads(body1)
        d2 = json.loads(body2)
        self.assertEqual(d1["total"], d2["total"], "total 跨页必须一致")
        self.assertGreaterEqual(d1["total"], 0, "无 token 时用户隔离允许 total 为 0")

    def test_has_more_correct(self):
        """has_more = offset + len(items) < total."""
        status, body = _fetch("/render-jobs?page=1&limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body)
        items = data["items"]
        total = data["total"]
        offset = (data["page"] - 1) * data["limit"]
        expected_has_more = (offset + len(items)) < total
        self.assertEqual(
            data["has_more"], expected_has_more,
            "has_more 错: got=" + str(data["has_more"]) + " expect=" + str(expected_has_more),
        )

    def test_status_filter(self):
        """status=success 过滤生效 (items 全 success 或 total 缩)."""
        status_all, body_all = _fetch("/render-jobs?page=1&limit=50")
        status_filtered, body_filtered = _fetch("/render-jobs?page=1&limit=50&status=success")
        self.assertEqual(status_all, 200)
        self.assertEqual(status_filtered, 200)
        d_all = json.loads(body_all)
        d_filt = json.loads(body_filtered)
        self.assertLessEqual(
            d_filt["total"], d_all["total"],
            "status=success 过滤后 total 应 <= total_all",
        )
        for it in d_filt["items"]:
            self.assertEqual(it.get("status"), "success")


class WorkflowRunsPaginationTests(unittest.TestCase):
    """同样格式应在 workflow-runs 端点生效 (D2-2 第二步)."""

    def test_page_zero_returns_list(self):
        status, body = _fetch("/workflow-runs?page=0&limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, list, "page=0 返 list")

    def test_page_one_returns_wrapper(self):
        status, body = _fetch("/workflow-runs?page=1&limit=5")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIsInstance(data, dict, "page>=1 返 dict")
        for key in ("items", "total", "page", "limit", "has_more"):
            self.assertIn(key, data)


if __name__ == "__main__":
    unittest.main()
