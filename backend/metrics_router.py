"""Fliki 还原 — /metrics 路由 (P1: 加 user/tenant 维度)

设计目标:
- /metrics/summary 健康摘要 + 全局计数 (保留 /metrics 的 Prometheus 合约)
- /metrics/users 按 user_id 聚合 workflow_drafts + workflow_runs
- /metrics/users/{user_id} 单用户详情 (404 = 未使用过系统)
- /metrics/tenants 框架占位 (当前未启用 tenant, 显式返回说明)

注意: 全部端点不接 auth, 走内网 (同 /health). 后续如需开放外网, 加 Bearer 校验.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException


def create_router(get_db):
    """get_db 是 main.py 注入的 DB 连接工厂 (sqlite3.connect)."""
    router = APIRouter(prefix="/metrics", tags=["metrics"])

    @router.get("/summary")
    def global_metrics():
        """全局计数 + 资源健康，不覆盖现有 Prometheus /metrics."""
        import shutil, time
        from pathlib import Path
        from config import config
        try:
            du = shutil.disk_usage(str(Path(config["DATA_DIR"])))
            disk_free_gb = round(du.free / 1e9, 2)
        except Exception:
            disk_free_gb = None
        with get_db() as conn:
            counts = {
                "users": conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"],
                "workflow_drafts": conn.execute("SELECT COUNT(*) AS c FROM workflow_drafts").fetchone()["c"],
                "workflow_drafts_confirmed": conn.execute(
                    "SELECT COUNT(*) AS c FROM workflow_drafts WHERE status = 'confirmed'"
                ).fetchone()["c"],
                "scene_drafts": conn.execute("SELECT COUNT(*) AS c FROM scene_drafts").fetchone()["c"],
                "workflow_runs": conn.execute("SELECT COUNT(*) AS c FROM workflow_runs").fetchone()["c"],
                "workflow_runs_succeeded": conn.execute(
                    "SELECT COUNT(*) AS c FROM workflow_runs WHERE status = 'succeeded'"
                ).fetchone()["c"],
                "workflow_runs_failed": conn.execute(
                    "SELECT COUNT(*) AS c FROM workflow_runs WHERE status = 'failed'"
                ).fetchone()["c"],
            }
        return {
            "ts": int(time.time()),
            "disk_free_gb": disk_free_gb,
            "counts": counts,
            "tenants": 1,  # 单租户架构
        }

    @router.get("/users")
    def per_user_metrics():
        """按 user_id 聚合: 草稿数 / 跑任务数 / 确认数 / 失败数.

        未登录 (user_id IS NULL) 的归属到 'anonymous' bucket, 兼容 P0-3 user_id 隔离之前的旧数据.
        """
        with get_db() as conn:
            rows = conn.execute("""
                SELECT
                    COALESCE(user_id, 'anonymous') AS user_id,
                    COUNT(*) AS drafts_total,
                    SUM(CASE WHEN status = 'confirmed' THEN 1 ELSE 0 END) AS drafts_confirmed
                FROM workflow_drafts
                GROUP BY COALESCE(user_id, 'anonymous')
                ORDER BY drafts_total DESC
            """).fetchall()
            runs_rows = conn.execute("""
                SELECT
                    COALESCE(user_id, 'anonymous') AS user_id,
                    COUNT(*) AS runs_total,
                    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS runs_succeeded,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS runs_failed
                FROM workflow_runs
                GROUP BY COALESCE(user_id, 'anonymous')
                ORDER BY runs_total DESC
            """).fetchall()
        # 合并两份聚合 (同一 user_id 必出现)
        agg = {}
        for r in rows:
            agg[r["user_id"]] = {
                "user_id": r["user_id"],
                "drafts_total": int(r["drafts_total"]),
                "drafts_confirmed": int(r["drafts_confirmed"] or 0),
                "runs_total": 0,
                "runs_succeeded": 0,
                "runs_failed": 0,
            }
        for r in runs_rows:
            bucket = agg.setdefault(r["user_id"], {
                "user_id": r["user_id"],
                "drafts_total": 0,
                "drafts_confirmed": 0,
                "runs_total": 0,
                "runs_succeeded": 0,
                "runs_failed": 0,
            })
            bucket["runs_total"] = int(r["runs_total"])
            bucket["runs_succeeded"] = int(r["runs_succeeded"] or 0)
            bucket["runs_failed"] = int(r["runs_failed"] or 0)
        return {
            "users": list(agg.values()),
            "total_users": len(agg),
            "anonymous_drafts": agg.get("anonymous", {}).get("drafts_total", 0),
        }

    @router.get("/users/{user_id}")
    def user_detail(user_id: str):
        """单用户详情: 草稿列表 + 跑任务列表 (最多 20 条).

        若该 user_id 从未创建任何草稿或跑任务, 返 404.
        """
        with get_db() as conn:
            drafts = conn.execute(
                "SELECT id, title, status, updated_at FROM workflow_drafts WHERE user_id = ? ORDER BY updated_at DESC LIMIT 20",
                (user_id,),
            ).fetchall()
            runs = conn.execute(
                "SELECT id, workflow_draft_id, status, progress, created_at FROM workflow_runs WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
                (user_id,),
            ).fetchall()
        if not drafts and not runs:
            raise HTTPException(status_code=404, detail=f"User {user_id!r} has no activity")
        return {
            "user_id": user_id,
            "drafts": [dict(d) for d in drafts],
            "runs": [dict(r) for r in runs],
        }

    @router.get("/tenants")
    def tenants_overview():
        """Tenant 维度框架占位. 当前架构单租户, 所有 user 共享同一 schemas."""
        return {
            "tenants": [
                {
                    "tenant_id": "default",
                    "name": "Default",
                    "is_active": True,
                    "user_count": 1,
                }
            ],
            "total": 1,
            "note": "Multi-tenant 暂未启用; users 表暂未带 tenant_id 字段. 启用时需 schema 迁移 + main.py 加 tenant 路由前缀.",
        }

    return router
