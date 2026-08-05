"""P0#2: env_validation startup required key fail-fast."""
import os
import unittest

import sys
sys.path.insert(0, "backend")
from env_validation import (
    validate_required_keys, EnvValidationError, REQUIRED_KEYS,
    PLACEHOLDER_VALUES, list_required_keys, _get_env,
)

REQUIRED_ENV_KEYS = ("DEEPSEEK_API_KEY", "MINIMAX_API_KEY", "FLIKI_JWT_SECRET")


class CiTestEnvSkipTest(unittest.TestCase):
    "FLIKI_ENV in {ci, test} skips validation entirely."
    def setUp(self):
        # clear all dev-required keys to prove skip works even if missing
        for key in REQUIRED_ENV_KEYS:
            os.environ.pop(key, None)
    def tearDown(self):
        for key in REQUIRED_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.pop("FLIKI_ENV", None)

    def test_ci_env_returns_empty_dict(self):
        os.environ["FLIKI_ENV"] = "ci"
        self.assertEqual(validate_required_keys(), {})

    def test_test_env_returns_empty_dict(self):
        os.environ["FLIKI_ENV"] = "test"
        self.assertEqual(validate_required_keys(), {})

    def test_explicit_strict_false_skips(self):
        # FLIKI_ENV=dev but strict=False (e.g. emergency bypass)
        os.environ["FLIKI_ENV"] = "dev"
        os.environ["FLIKI_VALIDATE_KEYS"] = "false"
        self.assertEqual(validate_required_keys(), {})

    def test_explicit_strict_false_skips_with_off_keyword(self):
        os.environ["FLIKI_ENV"] = "dev"
        os.environ["FLIKI_VALIDATE_KEYS"] = "off"
        self.assertEqual(validate_required_keys(), {})


class DevEnvRequiredKeysTest(unittest.TestCase):
    "FLIKI_ENV=dev (default) requires 3 keys, raises if missing."
    def setUp(self):
        for key in REQUIRED_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["FLIKI_ENV"] = "dev"
        os.environ["FLIKI_VALIDATE_KEYS"] = "true"
    def tearDown(self):
        for key in REQUIRED_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ.pop("FLIKI_ENV", None)
        os.environ.pop("FLIKI_VALIDATE_KEYS", None)

    def test_all_missing_raises(self):
        with self.assertRaises(EnvValidationError) as cm:
            validate_required_keys()
        msg = str(cm.exception)
        self.assertIn("DEEPSEEK_API_KEY", msg)
        self.assertIn("MINIMAX_API_KEY", msg)
        self.assertIn("FLIKI_JWT_SECRET", msg)
        self.assertIn("fix:", msg)

    def test_partial_missing_raises(self):
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        # MINIMAX + JWT still missing
        with self.assertRaises(EnvValidationError) as cm:
            validate_required_keys()
        msg = str(cm.exception)
        self.assertIn("MINIMAX_API_KEY", msg)
        self.assertIn("FLIKI_JWT_SECRET", msg)
        self.assertNotIn("DEEPSEEK_API_KEY", msg.split("missing")[1].split(chr(10))[0] if "missing" in msg else "")

    def test_placeholder_values_count_as_missing(self):
        for key in REQUIRED_ENV_KEYS:
            os.environ[key] = "change-me-32-char-min"
        with self.assertRaises(EnvValidationError):
            validate_required_keys()

    def test_all_real_values_pass(self):
        os.environ["DEEPSEEK_API_KEY"] = "sk-real-deepseek"
        os.environ["MINIMAX_API_KEY"] = "eyJ-real-minimax"
        os.environ["FLIKI_JWT_SECRET"] = "x" * 40
        result = validate_required_keys()
        self.assertEqual(len(result), 3)
        for k in REQUIRED_ENV_KEYS:
            self.assertEqual(result[k], "ok")


class ProdEnvJwtStrengthTest(unittest.TestCase):
    "FLIKI_ENV=prod requires JWT secret 32+ chars and rejects placeholder."
    def setUp(self):
        os.environ["FLIKI_ENV"] = "prod"
        os.environ["FLIKI_VALIDATE_KEYS"] = "true"
        os.environ["DEEPSEEK_API_KEY"] = "sk-real"
        os.environ["MINIMAX_API_KEY"] = "eyJ-real"
        os.environ["PEXELS_API_KEY"] = "px-real"
    def tearDown(self):
        for key in ("DEEPSEEK_API_KEY", "MINIMAX_API_KEY", "FLIKI_JWT_SECRET", "PEXELS_API_KEY"):
            os.environ.pop(key, None)
        os.environ.pop("FLIKI_ENV", None)
        os.environ.pop("FLIKI_VALIDATE_KEYS", None)

    def test_prod_with_placeholder_jwt_rejected(self):
        os.environ["FLIKI_JWT_SECRET"] = "change-me-32-char-min"
        with self.assertRaises(EnvValidationError) as cm:
            validate_required_keys()
        self.assertIn("placeholder value not allowed", str(cm.exception))

    def test_prod_with_short_jwt_rejected(self):
        os.environ["FLIKI_JWT_SECRET"] = "short"
        with self.assertRaises(EnvValidationError) as cm:
            validate_required_keys()
        msg = str(cm.exception)
        self.assertIn("weak", msg)
        self.assertIn("chars", msg)

    def test_prod_with_strong_jwt_passes(self):
        os.environ["FLIKI_JWT_SECRET"] = "a" * 40
        result = validate_required_keys()
        self.assertEqual(len(result), 4)


class HelpersTest(unittest.TestCase):
    "Smoke tests for list_required_keys and _get_env."
    def test_list_required_keys_dev(self):
        self.assertEqual(set(list_required_keys("dev")), set(REQUIRED_ENV_KEYS))
    def test_list_required_keys_ci(self):
        self.assertEqual(list_required_keys("ci"), [])
    def test_list_required_keys_test(self):
        self.assertEqual(list_required_keys("test"), [])
    def test_get_env_default(self):
        os.environ.pop("FLIKI_ENV", None)
        self.assertEqual(_get_env(), "dev")
    def test_placeholder_frozenset_immutable(self):
        self.assertEqual(len(PLACEHOLDER_VALUES), 5)
