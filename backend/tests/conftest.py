"""Backend test conftest (rev36 P0 CI fix).

在每个 test session 启动时确保 DB schema 已 init + users 表 + 必要的 seed.
- 兼容 unittest discover (ci.yml backend job 用) 和 pytest (本地).
- 幂等: init_db/ensure_users_table 用 CREATE IF NOT EXISTS, 可重复执行.
- live-HTTP tests (D1/D2/health/pagination/p0_security.backend_alive) 在 CI 需 backend 在 5181 监听.
  yml 加 background 启 backend + curl /health wait, 见 .github/workflows/ci.yml.
- TestClient tests (auth_rate_limit 等) 跳过 live backend 依赖, 但需要 users 表存在.
"""
import os
import sys

os.environ.setdefault("FLIKI_ENV", "dev")
os.environ.setdefault("FLIKI_JWT_SECRET", "ci-test-secret-32chars-padding-xx")

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TESTS_DIR)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


def _ensure_db_ready():
    """Idempotent: init_db + ensure_users_table + seed providers/voices."""
    try:
        from db.connection import init_db, get_db
        from auth_router import ensure_users_table
        from config import DATA_DIR
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        init_db()
        ensure_users_table()
        try:
            from main import seed_runtime_providers, ensure_voices
            with get_db() as conn:
                seed_runtime_providers(conn)
                ensure_voices(conn)
        except Exception as e:
            print("[conftest] seed warning:", e)
    except Exception as e:
        print("[conftest] init warning:", e)


# 导入 conftest 时立即执行一次 (兼容 unittest discover)
_ensure_db_ready()


try:
    import pytest  # noqa: F401

    def pytest_configure(config):  # noqa: ARG001
        _ensure_db_ready()
except ImportError:
    pass
