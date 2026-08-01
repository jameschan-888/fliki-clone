"""rev35 阶段 2 P0.1: db 连接 + schema 初始化.

get_db() 返回 sqlite3.Connection (row_factory=Row).
init_db() 读 schema.sql + ALTER TABLE 兼容, 返回是否发生迁移 (用于 lifespan 日志).

keep_old_main_api: 函数签名与 main.py 原版完全一致 (无 yield-based Depends 改造),
以便 569 个测试零修改即可切换.
"""
import sqlite3
import time
from pathlib import Path

from config import config

def get_db():
    conn = sqlite3.connect(config["DB_PATH"])
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    schema = Path(__file__).parent / "schema.sql"
    conn = get_db()
    try:
        conn.executescript(schema.read_text(encoding="utf-8"))
        migrated = False
        for table, col_defs in (
            ("scene_drafts", (("voice", "TEXT NOT NULL DEFAULT \"zh-CN-XiaoxiaoNeural\""),
                              ("avatar", "TEXT"),
                              ("avatar_layout", "TEXT"),
                              ("template_id", "TEXT"),
                              ("template_fields", "TEXT"),
                              ("stock_url", "TEXT"),
                              ("camera_motion", "TEXT NOT NULL DEFAULT \"zoom-in\""),
                              ("video_aspect", "TEXT NOT NULL DEFAULT \"16:9\""),
                              ("video_transition_mode", "TEXT NOT NULL DEFAULT \"fade\""),
                              ("media_width", "INTEGER NOT NULL DEFAULT 1280"),
                              ("media_height", "INTEGER NOT NULL DEFAULT 720"),
                              ("subtitle_display", "TEXT"),
                              ("subtitle_spoken", "TEXT"))),
        ):
            tcols = {row["name"] for row in conn.execute("PRAGMA table_info(" + table + ")").fetchall()}
            if not tcols:
                continue
            for col, decl in col_defs:
                if col not in tcols:
                    conn.execute("ALTER TABLE " + table + " ADD COLUMN " + col + " " + decl)
                    migrated = True
        for table in ("workflow_drafts", "workflow_runs", "render_jobs"):
            tcols = {row["name"] for row in conn.execute("PRAGMA table_info(" + table + ")").fetchall()}
            if not tcols:
                continue
            if "user_id" not in tcols:
                conn.execute("ALTER TABLE " + table + " ADD COLUMN user_id TEXT")
                migrated = True
            if "user_id" in tcols:
                for idx_sql in (
                    "CREATE INDEX IF NOT EXISTS idx_workflow_drafts_user ON workflow_drafts(user_id, updated_at DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_workflow_runs_user ON workflow_runs(user_id, created_at DESC)",
                    "CREATE INDEX IF NOT EXISTS idx_render_jobs_user ON render_jobs(user_id, created_at DESC)",
                ):
                    pass
                if table == "workflow_drafts":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_drafts_user ON workflow_drafts(user_id, updated_at DESC)")
                elif table == "workflow_runs":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_runs_user ON workflow_runs(user_id, created_at DESC)")
                elif table == "render_jobs":
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_render_jobs_user ON render_jobs(user_id, created_at DESC)")
        if migrated:
            conn.commit()
        return migrated
    finally:
        conn.close()
