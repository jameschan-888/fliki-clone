import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import provider_config


class ProviderEnvPersistTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env_file = Path(self.tmp.name) / ".env"
        self.db_file = Path(self.tmp.name) / "app.db"
        self._saved_env = {k: os.environ[k] for k in list(os.environ) if k == "PEXELS_API_KEY" or k.startswith("FLIKI_PROVIDER_")}
        self._saved_env_path = provider_config._ENV_PATH
        import main as _main
        self._saved_db_path = _main.config["DB_PATH"]
        for k in list(self._saved_env):
            os.environ.pop(k, None)
        _main.config["DB_PATH"] = str(self.db_file)
        provider_config._ENV_PATH = self.env_file
        if self.env_file.exists():
            self.env_file.unlink()
        if self.db_file.exists():
            self.db_file.unlink()
        _main.init_db()

    def tearDown(self):
        import main as _main
        _main.config["DB_PATH"] = self._saved_db_path
        provider_config._ENV_PATH = self._saved_env_path
        for k in list(os.environ):
            if k == "PEXELS_API_KEY" or k.startswith("FLIKI_PROVIDER_"):
                os.environ.pop(k, None)
        for k, v in self._saved_env.items():
            os.environ[k] = v
        self.tmp.cleanup()

    def test_persist_writes_managed_block_and_reloads(self):
        for k in ["PEXELS_API_KEY","FLIKI_PROVIDER_PEXELS_API_KEY"]:
            os.environ.pop(k, None)
        self.env_file.write_text(
            "JWT_SECRET=keep-this-value\nOTHER_SETTING=enabled\n",
            encoding="utf-8",
        )
        managed = provider_config._load_managed_env()
        managed["FLIKI_PROVIDER_PEXELS_API_KEY"] = "abc1234567890"
        provider_config._persist_managed_env(managed)
        text = self.env_file.read_text(encoding="utf-8")
        self.assertIn("JWT_SECRET=keep-this-value", text)
        self.assertIn("OTHER_SETTING=enabled", text)
        self.assertIn("FLIKI_PROVIDER_PEXELS_API_KEY=abc1234567890", text)
        self.assertIn("# Fliki managed provider keys", text)
        reloaded = provider_config.hydrate_env_from_disk()
        self.assertEqual(reloaded["FLIKI_PROVIDER_PEXELS_API_KEY"], "abc1234567890")
        self.assertEqual(os.environ["FLIKI_PROVIDER_PEXELS_API_KEY"], "abc1234567890")

    def test_update_persists_key_and_payload_reports_managed(self):
        os.environ.pop("PEXELS_API_KEY", None)
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        with mock.patch("main.hydrate_env_from_disk", lambda: {}):
            r = client.put("/provider-configs/stock/pexels", json={"api_key": "persist-9876543210"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["has_api_key"], True)
        self.assertEqual(r.json()["source"], "managed")
        self.assertTrue(r.json()["persist"])
        text = self.env_file.read_text(encoding="utf-8")
        self.assertIn("FLIKI_PROVIDER_PEXELS_API_KEY=persist-9876543210", text)

    def test_reload_after_purge_env(self):
        os.environ.pop("PEXELS_API_KEY", None)
        self.env_file.write_text("FLIKI_PROVIDER_PEXELS_API_KEY=reload-12345678" + chr(10), encoding="utf-8")
        provider_config.hydrate_env_from_disk()
        self.assertEqual(os.environ["FLIKI_PROVIDER_PEXELS_API_KEY"], "reload-12345678")
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        with mock.patch("main.hydrate_env_from_disk", lambda: {"FLIKI_PROVIDER_PEXELS_API_KEY": "reload-12345678"}):
            os.environ["PEXELS_API_KEY"] = "reload-12345678"
            try:
                r = client.get("/provider-configs")
            finally:
                os.environ.pop("PEXELS_API_KEY", None)
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.json() if x["name"] == "pexels")
        self.assertTrue(row["has_api_key"])
        self.assertEqual(row["api_key_masked"], "relo********5678")
        self.assertEqual(row["source"], "managed")
        self.assertTrue(row["persist"])

    def test_key_source_process_when_only_in_environ(self):
        for k in ["PEXELS_API_KEY","FLIKI_PROVIDER_PEXELS_API_KEY"]:
            os.environ.pop(k, None)
        os.environ["PEXELS_API_KEY"] = "env-1234567890"
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        with mock.patch("main.hydrate_env_from_disk", lambda: {}):
            r = client.get("/provider-configs")
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.json() if x["name"] == "pexels")
        self.assertEqual(row["source"], "env")
        self.assertFalse(row["persist"])

    def test_persist_false_skips_dotenv_write(self):
        # P5E: persist=false -> 只注入进程, .env 不落盘.
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        with mock.patch("main.hydrate_env_from_disk", lambda: {}):
            r = client.put(
                "/provider-configs/stock/pexels",
                json={"api_key": "temp-only-1234567890", "persist": False},
            )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["has_api_key"])
        self.assertFalse(body["persist"])
        self.assertEqual(body["source"], "env")
        self.assertEqual(os.environ["PEXELS_API_KEY"], "temp-only-1234567890")
        text = self.env_file.read_text(encoding="utf-8") if self.env_file.exists() else ""
        self.assertNotIn("FLIKI_PROVIDER_PEXELS_API_KEY", text)

    def test_delete_secret_clears_managed_block(self):
        # P5E: DELETE /provider-configs/.../secret 清掉 .env 与进程 env.
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        with mock.patch("main.hydrate_env_from_disk", lambda: {}):
            r1 = client.put(
                "/provider-configs/stock/pexels",
                json={"api_key": "to-be-deleted-1234"},
            )
        self.assertEqual(r1.status_code, 200)
        self.assertTrue(r1.json()["persist"])
        text = self.env_file.read_text(encoding="utf-8")
        self.assertIn("FLIKI_PROVIDER_PEXELS_API_KEY=to-be-deleted-1234", text)
        with mock.patch("main.hydrate_env_from_disk", lambda: {}):
            r2 = client.delete("/provider-configs/stock/pexels/secret")
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json()["removed"], True)
        self.assertEqual(r2.json()["env_name"], "PEXELS_API_KEY")
        self.assertNotIn("FLIKI_PROVIDER_PEXELS_API_KEY", self.env_file.read_text(encoding="utf-8"))
        self.assertNotIn("PEXELS_API_KEY", os.environ)
        self.assertNotIn("FLIKI_PROVIDER_PEXELS_API_KEY", os.environ)

    def test_hydrate_after_dotenv_change_simulates_restart(self):
        # P5E: .env 写好后, hydrate 模拟重启可恢复 env, source=managed.
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)
        # 直接写 .env 模拟"上一次运行保存"的密钥.
        self.env_file.write_text(
            "# Fliki managed provider keys (auto, do not edit by hand)\n"
            "FLIKI_PROVIDER_PEXELS_API_KEY=after-restart-9876543210\n",
            encoding="utf-8",
        )
        # 重启: 不带 env, 仅 hydrate.
        os.environ.pop("PEXELS_API_KEY", None)
        os.environ.pop("FLIKI_PROVIDER_PEXELS_API_KEY", None)
        provider_config.hydrate_env_from_disk()
        self.assertEqual(os.environ["FLIKI_PROVIDER_PEXELS_API_KEY"], "after-restart-9876543210")
        with mock.patch("main.hydrate_env_from_disk", lambda: {}):
            r = client.get("/provider-configs")
        self.assertEqual(r.status_code, 200)
        row = next(x for x in r.json() if x["name"] == "pexels")
        self.assertTrue(row["has_api_key"])
        self.assertEqual(row["source"], "managed")
        self.assertTrue(row["persist"])
        # mask 不回传明文.
        self.assertEqual(row["api_key_masked"], "afte********3210")
        self.assertNotIn("after-restart-9876543210", str(row))

if __name__ == "__main__":
    unittest.main()
