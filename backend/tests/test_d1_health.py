"""rev24 阶段 D D1-4: /health 增强 (cpu/disk/queue)."""
import json
import unittest
import urllib.request

BACKEND = "http://127.0.0.1:5181"


class D1HealthTests(unittest.TestCase):
    def test_health_basic(self):
        with urllib.request.urlopen(BACKEND + "/health", timeout=5) as r:
            self.assertEqual(r.status, 200)
            data = json.loads(r.read().decode("utf-8"))

    def test_health_status_ok(self):
        with urllib.request.urlopen(BACKEND + "/health", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")

    def test_health_has_cpu_count(self):
        with urllib.request.urlopen(BACKEND + "/health", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertIn("cpu_count", data)
            self.assertIsInstance(data["cpu_count"], int)
            self.assertGreaterEqual(data["cpu_count"], 1)

    def test_health_has_disk_free(self):
        with urllib.request.urlopen(BACKEND + "/health", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertIn("disk_free_gb", data)
            self.assertIn("disk_total_gb", data)
            if data["disk_free_gb"] is not None:
                self.assertGreaterEqual(data["disk_free_gb"], 0.0)
                self.assertGreaterEqual(data["disk_total_gb"], data["disk_free_gb"])

    def test_health_has_render_queue(self):
        with urllib.request.urlopen(BACKEND + "/health", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertIn("render_queue", data)
            rq = data["render_queue"]
            self.assertIn("queued", rq)
            self.assertIn("active", rq)
            self.assertIsInstance(rq["queued"], int)
            self.assertIsInstance(rq["active"], int)
            self.assertGreaterEqual(rq["queued"], 0)
            self.assertGreaterEqual(rq["active"], 0)

    def test_health_has_timestamp(self):
        import time
        with urllib.request.urlopen(BACKEND + "/health", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
            self.assertIn("ts", data)
            self.assertAlmostEqual(data["ts"], time.time(), delta=5)


if __name__ == "__main__":
    unittest.main()
