"""rev24 阶段 D D1-4: /health 增强 (cpu/disk/queue)."""
import time
import unittest

from fastapi.testclient import TestClient
from main import app


class D1HealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def _data(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_health_basic(self):
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_health_status_ok(self):
        self.assertEqual(self._data().get("status"), "ok")

    def test_health_has_cpu_count(self):
        data = self._data()
        self.assertIn("cpu_count", data)
        self.assertIsInstance(data["cpu_count"], int)
        self.assertGreaterEqual(data["cpu_count"], 1)

    def test_health_has_disk_free(self):
        data = self._data()
        self.assertIn("disk_free_gb", data)
        self.assertIn("disk_total_gb", data)
        if data["disk_free_gb"] is not None:
            self.assertGreaterEqual(data["disk_free_gb"], 0.0)
            self.assertGreaterEqual(data["disk_total_gb"], data["disk_free_gb"])

    def test_health_has_render_queue(self):
        data = self._data()
        self.assertIn("render_queue", data)
        queue = data["render_queue"]
        self.assertIn("queued", queue)
        self.assertIn("active", queue)
        self.assertIsInstance(queue["queued"], int)
        self.assertIsInstance(queue["active"], int)
        self.assertGreaterEqual(queue["queued"], 0)
        self.assertGreaterEqual(queue["active"], 0)

    def test_health_has_timestamp(self):
        data = self._data()
        self.assertIn("ts", data)
        self.assertAlmostEqual(data["ts"], time.time(), delta=5)


if __name__ == "__main__":
    unittest.main()
