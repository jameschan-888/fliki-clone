"""P2-Hardening: 启动时 JWT_SECRET 校验.

import main 时会触发 validate_jwt_secret, 这里覆盖 4 个场景:
  1. dev + 默认 secret: stderr 警告, 不 raise
  2. dev + 自定义强 secret: silent OK
  3. prod + 默认 secret: raise RuntimeError
  4. prod + 短 secret: raise RuntimeError
  5. prod + 强 secret: silent OK
"""
import importlib
import os
import sys
import unittest
from unittest import mock


class _AuthSecretValidationTest(unittest.TestCase):
    def setUp(self):
        self._saved = {}
        for key in ("FLIKI_ENV", "FLIKI_JWT_SECRET"):
            self._saved[key] = os.environ.pop(key, None)
        sys.modules.pop("main", None)

    def tearDown(self):
        sys.modules.pop("main", None)
        for key, val in self._saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def _reload_main(self):
        sys.path.insert(0, ".")
        return importlib.import_module("main")

    def test_dev_default_warns_but_continues(self):
        os.environ.pop("FLIKI_ENV", None)
        os.environ.pop("FLIKI_JWT_SECRET", None)
        with mock.patch("sys.stderr") as stderr:
            main = self._reload_main()
        self.assertTrue(any("placeholder" in str(call) for call in stderr.write.call_args_list))
        self.assertGreater(len(main.app.routes), 0)

    def test_dev_strong_secret_silent(self):
        os.environ.pop("FLIKI_ENV", None)
        os.environ["FLIKI_JWT_SECRET"] = "abcdefghijklmnopqrstuvwxyz1234567890ABCD"
        with mock.patch("sys.stderr") as stderr:
            main = self._reload_main()
        writes = [str(c) for c in stderr.write.call_args_list]
        self.assertFalse(any("placeholder" in w or "recommend" in w for w in writes))
        self.assertGreater(len(main.app.routes), 0)

    def test_prod_default_raises(self):
        os.environ["FLIKI_ENV"] = "prod"
        os.environ.pop("FLIKI_JWT_SECRET", None)
        with self.assertRaises(RuntimeError) as ctx:
            self._reload_main()
        self.assertIn("placeholder", str(ctx.exception))

    def test_prod_short_secret_raises(self):
        os.environ["FLIKI_ENV"] = "prod"
        os.environ["FLIKI_JWT_SECRET"] = "short"
        with self.assertRaises(RuntimeError) as ctx:
            self._reload_main()
        self.assertIn("length", str(ctx.exception).lower())

    def test_prod_strong_secret_ok(self):
        os.environ["FLIKI_ENV"] = "prod"
        os.environ["FLIKI_JWT_SECRET"] = "abcdefghijklmnopqrstuvwxyz1234567890ABCD"
        with mock.patch("sys.stderr") as stderr:
            main = self._reload_main()
        writes = [str(c) for c in stderr.write.call_args_list]
        self.assertFalse(any("placeholder" in w or "recommend" in w for w in writes))
        self.assertGreater(len(main.app.routes), 0)


if __name__ == "__main__":
    unittest.main()
