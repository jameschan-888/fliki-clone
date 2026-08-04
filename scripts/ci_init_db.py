"""CI: fresh-checkout DB schema init + seed (rev36 P0).

幂等: 跑多次效果相同 (CREATE IF NOT EXISTS). 失败 exit 1.
用法: python scripts/ci_init_db.py
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(str(BACKEND))

from config import DATA_DIR  # noqa: E402
DATA_DIR.mkdir(parents=True, exist_ok=True)

from db.connection import init_db, get_db  # noqa: E402
from auth_router import ensure_users_table  # noqa: E402
from main import seed_runtime_providers, ensure_voices  # noqa: E402

migrated = init_db()
ensure_users_table()
with get_db() as conn:
    seed_runtime_providers(conn)
    ensure_voices(conn)
print(f"[ci_init_db] OK, migrated={migrated}, data_dir={DATA_DIR}")
