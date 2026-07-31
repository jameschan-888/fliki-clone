"""Unit tests for the rev24 cloud-renderer provider contract (stage C)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import workers.cloud_renderer as cr


class CloudProviderContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.props = Path(self.tmp.name) / "props.json"
        self.props.write_text(
            '{"scenes": [{}], "durationInSeconds": 1.5}', encoding="utf-8"
        )

    def test_get_provider_resolves_mock_by_default(self):
        prov = cr.get_provider("mock")
        self.assertIsInstance(prov, cr.MockProvider)
        self.assertEqual(prov.name, "mock")

    def test_get_provider_resolves_lambda_class(self):
        prov = cr.get_provider("lambda")
        self.assertIsInstance(prov, cr.LambdaProvider)
        self.assertEqual(prov.name, "lambda")

    def test_get_provider_rejects_unknown(self):
        with self.assertRaises(RuntimeError):
            cr.get_provider("does-not-exist-12345")

    def test_lambda_provider_submit_requires_url(self):
        prov = cr.LambdaProvider()
        with self.assertRaises(RuntimeError):
            prov.submit(str(self.props), {})

    def test_lambda_provider_poll_misconfigured_returns_failed(self):
        prov = cr.LambdaProvider()
        handle = cr.RenderHandle(provider="lambda", external_id="x")
        ev = prov.poll(handle)
        self.assertEqual(ev.status, "failed")

    def test_lambda_provider_uses_requests_post(self):
        prov = cr.LambdaProvider()
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {"jobId": "abc-123", "status": "queued"}
        fake_requests = MagicMock()
        fake_requests.post.return_value = fake_resp
        fake_requests.get.return_value = fake_resp
        fake_requests.exceptions = cr.requests.exceptions if cr.requests else None
        with patch.dict(os.environ, {"CLOUD_LAMBDA_URL": "https://lambda.example.com"}):
            with patch.object(cr, "requests", fake_requests):
                handle = prov.submit(str(self.props), {"job_id": "job-1"})
        self.assertEqual(handle.external_id, "abc-123")
        self.assertEqual(handle.provider, "lambda")
        fake_requests.post.assert_called_once()
        called_url = fake_requests.post.call_args[0][0]
        self.assertTrue(called_url.endswith("/renders"))

    def test_lambda_poll_maps_status_and_progress(self):
        prov = cr.LambdaProvider()
        fake_resp = MagicMock()
        fake_resp.raise_for_status.return_value = None
        fake_resp.json.return_value = {
            "status": "running",
            "progress": 42,
            "message": "rendering frame",
            "outputUrl": "https://x/y.mp4",
        }
        fake_requests = MagicMock()
        fake_requests.get.return_value = fake_resp
        with patch.dict(os.environ, {"CLOUD_LAMBDA_URL": "https://lambda.example.com"}):
            with patch.object(cr, "requests", fake_requests):
                ev = prov.poll(cr.RenderHandle(provider="lambda", external_id="x"))
        self.assertEqual(ev.status, "running")
        self.assertEqual(ev.progress, 42)
        self.assertEqual(ev.output_url, "https://x/y.mp4")


class RunProviderRenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.props = Path(self.tmp.name) / "props.json"
        self.props.write_text('{"scenes":[{}],"durationInSeconds":1.0}', encoding="utf-8")
        self.out_dir = Path(self.tmp.name) / "out"

    def test_run_provider_render_returns_failure_for_unknown_provider(self):
        with patch.dict(os.environ, {"CLOUD_RENDER_PROVIDER": "nope-xyz"}):
            cr._PROVIDER_CACHE.clear()
            ok, msg, path, started, finished = cr.run_provider_render(
                "j1", str(self.props), str(self.out_dir), "720p",
                provider_name="nope-xyz",
            )
        self.assertFalse(ok)
        self.assertIn("nope-xyz", msg)

    def test_run_provider_render_invokes_provider_with_payload(self):
        prov = MagicMock(spec=cr.CloudProvider)
        prov.submit.return_value = cr.RenderHandle(provider="mock", external_id="h1")
        prov.poll.side_effect = [
            cr.ProgressEvent(status="running", progress=10),
            cr.ProgressEvent(status="success", progress=100, output_url=None),
        ]
        prov.download.return_value = True
        with patch.object(cr, "get_provider", return_value=prov):
            ok, msg, path, started, finished = cr.run_provider_render(
                "j2", str(self.props), str(self.out_dir), "720p",
            )
        self.assertTrue(ok, msg=msg)
        prov.submit.assert_called_once()
        self.assertEqual(prov.submit.call_args[0][0], str(self.props))
        payload = prov.submit.call_args[0][1]
        self.assertEqual(payload["job_id"], "j2")
        self.assertEqual(payload["resolution"], "720p")
        self.assertGreaterEqual(prov.poll.call_count, 1)


if __name__ == "__main__":
    unittest.main()
