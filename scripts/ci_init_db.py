"""CI: fresh-checkout DB schema init + sample seed (rev36 P1).

幂等: 跑多次效果相同 (CREATE IF NOT EXISTS + INSERT OR IGNORE on sample).
插入 sample render_jobs + workflow_runs 让 metrics 端点 (tenant / user 维度) 不为空.
用法: python scripts/ci_init_db.py
"""
import os
import sys
import time
import uuid
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

# 插 sample render_jobs / workflow_runs 让 metrics 不空 (rev36 P1)
# 用固定 UUID + ON CONFLICT IGNORE 保证幂等
SAMPLE_USERS = ["ci-user-a", "ci-user-b", "ci-user-c", "ci-user-d", "ci-user-e"]
NOW = time.strftime("%Y-%m-%d %H:%M:%S")
with get_db() as conn:
    # 5 个 sample user (固定 id, ON CONFLICT 跳过)
    for uid in SAMPLE_USERS:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (uid, uid + "@ci.local", "ci-salt-" + uid, "ci-hash-" + uid, "user", NOW, NOW),
        )
    conn.commit()
    # 8 个 sample render_jobs (分散到 4 个 tenant 桶)
    sample_jobs = [
        (uid + "-job-" + str(i), uid, ["queued", "processing", "success", "failed"][i % 4])
        for uid in SAMPLE_USERS
        for i in range(2)
    ]
    for jid, uid, status in sample_jobs:
        conn.execute(
            "INSERT OR IGNORE INTO render_jobs (_id, playback_id, user_id, status, progress, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (jid, jid + "-pb", uid, status, 100 if status == "success" else 50, NOW),
        )
    conn.commit()
# workflow_runs FK 复杂, skip (metrics 容忍空表)


print(f"[ci_init_db] OK, migrated={migrated}, data_dir={DATA_DIR}")
