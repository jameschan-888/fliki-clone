"""rev35 P0-2: RequestID + JSON 日志中间件测试."""
import json
import logging
import os
import unittest

os.environ.setdefault("FLIKI_JWT_SECRET", "test-reqid-secret-32chars-padding-xx")
os.environ.setdefault("FLIKI_ENV", "dev")

from main import app  # noqa: E402
from fastapi.testclient import TestClient


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class RequestIdContractTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_request_id_propagated(self):
        response = self.client.get("/health", headers={"X-Request-ID": "req-abc-123"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("x-request-id"), "req-abc-123")

    def test_request_id_auto_generated(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        request_id = response.headers.get("x-request-id", "")
        self.assertTrue(request_id.startswith("req-"), request_id)
        self.assertGreaterEqual(len(request_id), 12)

    def test_request_id_present_on_error(self):
        response = self.client.get("/__nope_does_not_exist__")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(response.headers.get("x-request-id", "").startswith("req-"))


class JsonAccessLogTest(unittest.TestCase):
    """每个请求结束后, access logger 必须输出 1 条 JSON 行."""

    def setUp(self):
        self.client = TestClient(app)
        logger = logging.getLogger("fliki.access")
        logger.setLevel(logging.INFO)
        self.handler = _ListHandler()
        logger.addHandler(self.handler)

    def tearDown(self):
        logger = logging.getLogger("fliki.access")
        logger.removeHandler(self.handler)

    def test_access_log_emits_json(self):
        self.client.get("/health", headers={"X-Request-ID": "req-log-test"})
        matching = [r for r in self.handler.records if r.name == "fliki.access"]
        self.assertEqual(len(matching), 1)
        payload = json.loads(matching[0].getMessage())
        self.assertEqual(payload.get("request_id"), "req-log-test")
        self.assertEqual(payload.get("method"), "GET")
        self.assertEqual(payload.get("path"), "/health")
        self.assertEqual(payload.get("status"), 200)
        self.assertIn("duration_ms", payload)
