"""P0#2: startup required env key fail-fast validation.

Design:
  FLIKI_ENV in {ci, test} -> skip (CI uses mock + TestClient).
  FLIKI_ENV=dev -> require DEEPSEEK_API_KEY + MINIMAX_API_KEY + FLIKI_JWT_SECRET.
  FLIKI_ENV=prod -> same + JWT must be 32+ chars strong random (no placeholders).
  FLIKI_VALIDATE_KEYS=false -> force skip (emergency bypass).

Call from main.py lifespan first step. Raises EnvValidationError to block startup.
"""

import os

REQUIRED_KEYS = {
    "dev": {
        "DEEPSEEK_API_KEY": "DeepSeek text provider (workflow scene split + chat intent parse, R28)",
        "MINIMAX_API_KEY": "MiniMax video/image/tts/music multimodal provider",
        "FLIKI_JWT_SECRET": "JWT signing secret (>=32 chars, prod strong random)",
    },
    "prod": {
        "DEEPSEEK_API_KEY": "DeepSeek text provider (required)",
        "MINIMAX_API_KEY": "MiniMax multimodal provider (required)",
        "FLIKI_JWT_SECRET": "JWT signing secret (>=32 chars, placeholder not allowed)",
        "PEXELS_API_KEY": "Pexels stock video provider (required)",
    },
    "ci": {},
    "test": {},
}

PLACEHOLDER_VALUES = frozenset([
    "",
    "change-me-32-char-min",
    "change-me",
    "todo",
    "your-key-here",
])

JWT_MIN_LENGTH = 32


class EnvValidationError(RuntimeError):
    "Raised when required env keys are missing or weak. Includes actionable fix hints."


def _get_env() -> str:
    return (os.getenv("FLIKI_ENV") or "dev").lower()


def _is_strict() -> bool:
    flag = (os.getenv("FLIKI_VALIDATE_KEYS") or "").lower()
    return flag not in ("0", "false", "no", "off", "skip")


def validate_required_keys(env=None, strict=None) -> dict:
    """Check required env keys for the given FLIKI_ENV. Returns dict of key -> ok on success.

    Raises EnvValidationError with actionable fix instructions on missing/weak keys.
    Skips entirely for FLIKI_ENV in {ci, test} or when FLIKI_VALIDATE_KEYS is explicitly disabled.
    """
    if env is None:
        env = _get_env()
    if strict is None:
        strict = _is_strict()
    if env in ("ci", "test"):
        return {}
    if not strict:
        return {}
    required = REQUIRED_KEYS.get(env, REQUIRED_KEYS["dev"])
    if not required:
        return {}
    missing = []
    weak = []
    for key, desc in required.items():
        val = os.getenv(key, "").strip()
        if not val:
            missing.append(key)
            continue
        # JWT 专项: placeholder 在 prod 走 weak 路径, 不是 missing
        if key == "FLIKI_JWT_SECRET" and env == "prod" and val in PLACEHOLDER_VALUES:
            weak.append(key + " (placeholder value not allowed in prod, set real JWT secret)")
            continue
        if val in PLACEHOLDER_VALUES:
            missing.append(key)
            continue
        if key == "FLIKI_JWT_SECRET":
            if env == "prod" and len(val) < JWT_MIN_LENGTH:
                weak.append(key + " (" + str(len(val)) + " chars < " + str(JWT_MIN_LENGTH) + ")")
    if not missing and not weak:
        return {key: "ok" for key in required}
    lines = ["[env_validation] FLIKI_ENV=" + env + " startup required env check FAILED:"]
    if missing:
        lines.append("  missing: " + ", ".join(missing))
    if weak:
        lines.append("  weak: " + ", ".join(weak))
    lines.append("  missing keys purpose:")
    for key in (missing + [w.split(" (")[0] for w in weak]):
        desc = required.get(key, "")
        lines.append("    - " + key + ": " + desc)
    lines.append("  fix: copy backend/.env.example to backend/.env and fill real keys")
    lines.append("  emergency bypass: set FLIKI_VALIDATE_KEYS=false (startup will not abort, but first call will fail)")
    raise EnvValidationError(chr(10).join(lines))


def list_required_keys(env=None) -> list:
    """Return list of keys that would be checked for the given env. Useful for diagnostics + startup status endpoint.
    """
    if env is None:
        env = _get_env()
    return list(REQUIRED_KEYS.get(env, {}).keys())
