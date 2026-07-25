import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import main
from avatar_clone_router import create_router


def _build_app(tmp_dir):
    main.config["DB_PATH"] = str(Path(tmp_dir) / "app.db")
    main.init_db()
    get_db = main.get_db
    face_root = Path(tmp_dir) / "faces"
    audio_root = Path(tmp_dir) / "audios"
    output_root = Path(tmp_dir) / "outputs"
    for d in (face_root, audio_root, output_root):
        d.mkdir(parents=True, exist_ok=True)
    return create_router(get_db,
                         ref_face_dir=str(face_root),
                         audio_dir=str(audio_root),
                         output_dir=str(output_root)), get_db


class AvatarClonesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.router, self.get_db = _build_app(self.tmp.name)

    def tearDown(self):
        import gc; gc.collect()
        try: self.tmp.cleanup()
        except (PermissionError, OSError): pass

    def _fake_png(self, size=2048):
        return b"\x89PNG\r\n\x1a\n" + b"\x00" * (size - 8)

    def _post_face(self, name="Alice", face_payload=None, audio_payload=None, language="zh"):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        data = {"avatar_name": name, "language": language}
        files = [("ref_face", ("face.png", io.BytesIO(face_payload or self._fake_png()), "image/png"))]
        if audio_payload is not None:
            files.append(("ref_audio", ("audio.wav", io.BytesIO(audio_payload), "audio/wav")))
        return client.post("/avatar-clones", data=data, files=files)

    def test_list_clones_empty(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        r = client.get("/avatar-clones")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), [])

    def test_create_clone_persists_and_lists(self):
        r = self._post_face(audio_payload=b"RIFF" + b"\x10\x00" * 1024)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertIn("uuid", body)
        self.assertEqual(body["avatar_name"], "Alice")
        self.assertTrue(body["voice"].startswith("avatar:"))
        # Listing
        from fastapi.testclient import TestClient
        listed = TestClient(main.app).get("/avatar-clones").json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["uuid"], body["uuid"])

    def test_create_clone_rejects_invalid_face_ext(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        r = client.post(
            "/avatar-clones",
            data={"avatar_name": "Bob", "language": "zh"},
            files=[("ref_face", ("face.gif", io.BytesIO(b"GIF89a" + b"\x00" * 64), "image/gif"))],
        )
        self.assertEqual(r.status_code, 422)
        self.assertIn("extension", r.json()["message"])

    def test_create_clone_rejects_tiny_face(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        r = client.post(
            "/avatar-clones",
            data={"avatar_name": "x", "language": "zh"},
            files=[("ref_face", ("face.png", io.BytesIO(b"tiny"), "image/png"))],
        )
        self.assertEqual(r.status_code, 422)
        self.assertIn("small", r.json()["message"])

    def test_get_clone_404(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        r = client.get("/avatar-clones/no-such-uuid")
        self.assertEqual(r.status_code, 404)

    def test_delete_clone_removes_row_and_files(self):
        created = self._post_face(audio_payload=b"RIFF" + b"\x10\x00" * 512).json()
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        r = client.delete(f"/avatar-clones/{created['uuid']}")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["deleted"])
        self.assertFalse(Path(created["ref_face_path"]).exists())
        self.assertFalse(Path(created["ref_audio_path"]).exists())

    def test_synthesize_endpoint_404_for_missing_clone(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        r = client.post("/avatar-clones/no-such-uuid/synthesize")
        self.assertEqual(r.status_code, 404)

    def test_synthesize_endpoint_502_when_provider_fails(self):
        created = self._post_face(audio_payload=b"RIFF" + b"\x10\x00" * 512).json()
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        # Force provider.build_wav2lip_provider().synthesize to raise a ProviderError
        import avatar_clone_router as router_module
        from providers.avatar import wav2lip_onnx as provider_module
        with patch.object(router_module, "build_wav2lip_provider") as builder:
            instance = MagicMock()
            instance.synthesize.side_effect = provider_module.ProviderError("boom")
            builder.return_value = instance
            r = client.post(f"/avatar-clones/{created['uuid']}/synthesize")
        self.assertEqual(r.status_code, 502, r.text)
        self.assertIn("boom", r.json()["message"])

    def test_synthesize_endpoint_succeeds_with_mock_output(self):
        created = self._post_face(audio_payload=b"RIFF" + b"\x10\x00" * 512).json()
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        import avatar_clone_router as router_module
        from providers.avatar import wav2lip_onnx as provider_module

        def _write_mock_result(face_image_path=None, audio_path=None, destination_path=None, **_kw):
            dest_path = Path(destination_path)
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(b"MP4" + b"\x00" * 5000)
            return {"provider": "wav2lip_onnx", "mode": "static_avatar",
                    "fallback_used": True, "model_present": False, "elapsed_seconds": 0.1}

        with patch.object(router_module, "build_wav2lip_provider") as builder:
            instance = MagicMock()
            instance.synthesize.side_effect = _write_mock_result
            builder.return_value = instance
            r = client.post(f"/avatar-clones/{created['uuid']}/synthesize")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["fallback_used"])
        self.assertEqual(body["mode"], "static_avatar")
        self.assertEqual(body["output_url"], f"/avatar-clones/{created['uuid']}/output")
        # Output endpoint serves the file we just wrote
        r2 = client.get(body["output_url"])
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(int(r2.headers.get("content-length")), 5003)

    def test_health_endpoint_reports_no_dependencies(self):
        from fastapi.testclient import TestClient
        client = TestClient(main.app)
        r = client.get("/avatar-clones/provider/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["provider"], "wav2lip_onnx")
        self.assertIn("model_present", body)
        self.assertIn("dependency_warnings", body)
        # At least one of cv2/librosa will be missing on a bare install
