"""rev35 阶段 2 P0.4: /metrics / /characters / /providers + 4 个 helpers.

P0 拆分: 把 main.py 4 个分散 inline 段 (StyleOut + 4 helpers + metrics endpoint +
characters endpoint + providers endpoint + _emit_tenant_metrics) 集中搬到本模块.

所有 inline 使用的 @app.get 改为 @router.get, router mount 时用普通 include_router
(无 prefix).
"""
from fastapi import APIRouter, Depends, Request, Response
import sqlite3
from db.connection import get_db

def _resolve_con(con):
    """FastAPI injects con via Depends(get_db); direct calls (tests) pass Depends object.
    Detect & resolve via main.get_db() first (legacy test mock) then db.connection.get_db().
    """
    if hasattr(con, "execute") and hasattr(con, "close"):
        return con
    try:
        import main as _main
        return _main.get_db()
    except Exception:
        from db.connection import get_db as _gdb
        return _gdb()
from fastapi.responses import PlainTextResponse
import hashlib
import json
from pydantic import BaseModel, Field

from config import DEFAULT_PROVIDERS

router = APIRouter(tags=["analytics"])

class StyleOut(BaseModel):
    model_config = {"populate_by_name": True}
    id: str = Field(alias="_id")
    name: str
    key: str
    prefix: str | None = None
    suffix: str | None = None
    character_prompt: str | None = None
    composition: str | None = None
    image_prompt_direction: str | None = None
    video_prompt_direction: str | None = None
    thumbnail: str | None = None


def _top_users_by_activity(con, table, n=10):
    """rev24 阶段 D P1-A: top N users by total activity in a table; rest aggregated as 'other' cap.

    Defensive: if table missing user_id column or has no rows, return ([], 0).
    """
    try:
        tcols = {row["name"] for row in con.execute("PRAGMA table_info(" + table + ")").fetchall()}
        if "user_id" not in tcols:
            return ([], 0)
        rows = con.execute(
            "SELECT user_id, COUNT(*) AS cnt FROM " + table + " WHERE user_id IS NOT NULL GROUP BY user_id ORDER BY cnt DESC"
        ).fetchall()
        return ([(str(r[0]), int(r[1])) for r in rows[:n]], sum(int(r[1]) for r in rows[n:]))
    except Exception:
        return ([], 0)


def _emit_user_metrics(con, out):
    """rev24 阶段 D P1-A: emit Prometheus metrics with user/tenant dimension.

    Cardinality cap: top 10 users per table, others aggregated as user_id="other".
    Avoids high-cardinality explosion in TSDB.
    """
    TOP_N = 10

    # 1) render_jobs per user (top N + other)
    out.append("# HELP fliki_render_jobs_per_user_total Render jobs by user_id (top N + other bucket)")
    out.append("# TYPE fliki_render_jobs_per_user_total gauge")
    top_users, _other = _top_users_by_activity(con, "render_jobs", n=TOP_N)
    top_user_ids = {u for u, _ in top_users}
    per_user_status = con.execute(
        "SELECT user_id, status, COUNT(*) FROM render_jobs WHERE user_id IS NOT NULL GROUP BY user_id, status"
    ).fetchall()
    for user_id, status, cnt in per_user_status:
        bucket = user_id if user_id in top_user_ids else "other"
        out.append("fliki_render_jobs_per_user_total{user_id=\"" + str(bucket) + "\", status=\"" + str(status or "unknown") + "\"} " + str(cnt))
    out.append("")

    # 2) workflow_runs per user (top N + other)
    out.append("# HELP fliki_workflow_runs_per_user_total Workflow runs by user_id (top N + other bucket)")
    out.append("# TYPE fliki_workflow_runs_per_user_total gauge")
    top_users_r, _other_r = _top_users_by_activity(con, "workflow_runs", n=TOP_N)
    top_user_ids_r = {u for u, _ in top_users_r}
    per_user_status_r = con.execute(
        "SELECT user_id, status, COUNT(*) FROM workflow_runs WHERE user_id IS NOT NULL GROUP BY user_id, status"
    ).fetchall()
    for user_id, status, cnt in per_user_status_r:
        bucket = user_id if user_id in top_user_ids_r else "other"
        out.append("fliki_workflow_runs_per_user_total{user_id=\"" + str(bucket) + "\", status=\"" + str(status or "unknown") + "\"} " + str(cnt))
    out.append("")

    # 3) top N users by total jobs (rank 1..N)
    out.append("# HELP fliki_top_users_by_jobs Top N users by total render_jobs (rank 1..N)")
    out.append("# TYPE fliki_top_users_by_jobs gauge")
    for rank, (user_id, cnt) in enumerate(top_users, 1):
        out.append("fliki_top_users_by_jobs{user_id=\"" + str(user_id) + "\", rank=\"" + str(rank) + "\"} " + str(cnt))
    out.append("")

    # 4) active users in last 24h (distinct user_id with recent activity)
    out.append("# HELP fliki_active_users_24h Distinct users with activity in last 24h")
    out.append("# TYPE fliki_active_users_24h gauge")
    try:
        active_render = int(con.execute(
            "SELECT COUNT(DISTINCT user_id) FROM render_jobs WHERE user_id IS NOT NULL AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0] or 0)
    except Exception:
        active_render = 0
    try:
        active_run = int(con.execute(
            "SELECT COUNT(DISTINCT user_id) FROM workflow_runs WHERE user_id IS NOT NULL AND created_at >= datetime('now', '-1 day')"
        ).fetchone()[0] or 0)
    except Exception:
        active_run = 0
    out.append("fliki_active_users_24h{source=\"render_jobs\"} " + str(active_render))
    out.append("fliki_active_users_24h{source=\"workflow_runs\"} " + str(active_run))
    out.append("")


# ===== Phase 3-5: /metrics (Prometheus format) =====
def _safe_count(con, sql, params=()):
    try:
        row = con.execute(sql, params).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


@router.get("/metrics")
def metrics(con: sqlite3.Connection = Depends(get_db)):
    """Prometheus-compatible metrics endpoint.

    Counters (Gauge-based for point-in-time):
      - fliki_render_jobs_total{status=...} render_jobs by status
      - fliki_workflow_runs_total{status=...} workflow_runs by status
      - fliki_workflow_drafts_total drafts count
      - fliki_render_queue_active semaphore active slots
      - fliki_backend_up backend liveness (always 1)
    Plus user/tenant dimensional metrics via _emit_user_metrics / _emit_tenant_metrics.
    """
    out = []
    con = _resolve_con(con)
    try:
        # render_jobs by status
        try:
            for status, cnt in con.execute(
                "SELECT status, COUNT(*) FROM render_jobs GROUP BY status"
            ).fetchall():
                out.append('fliki_render_jobs_total{status="' + str(status or "unknown") + '"} ' + str(cnt))
        except Exception as e:
            out.append("# render_jobs_total error: " + str(e))
        out.append("")

        # workflow_runs by status
        try:
            for status, cnt in con.execute(
                "SELECT status, COUNT(*) FROM workflow_runs GROUP BY status"
            ).fetchall():
                out.append('fliki_workflow_runs_total{status="' + str(status or "unknown") + '"} ' + str(cnt))
        except Exception as e:
            out.append("# workflow_runs_total error: " + str(e))
        out.append("")

        # workflow_drafts total
        drafts = _safe_count(con, "SELECT count(*) FROM workflow_drafts")
        out.append('fliki_workflow_drafts_total ' + str(drafts))
        out.append("")

        # render_queue_active (proxy: count of active render processes)
        try:
            active = len(ACTIVE_RENDER_PROCESSES) if ACTIVE_RENDER_PROCESSES is not None else 0
        except Exception:
            active = 0
        out.append('fliki_render_queue_active ' + str(active))
        out.append("")

        # backend_up
        out.append('fliki_backend_up 1')
        out.append("")

        # user dimension (P1-A)
        try:
            _emit_user_metrics(con, out)
        except Exception as e:
            out.append("# _emit_user_metrics error: " + str(e))

        # tenant dimension (D1-1)
        try:
            _emit_tenant_metrics(con, out)
        except Exception as e:
            out.append("# _emit_tenant_metrics error: " + str(e))

        body = "\n".join(out) + "\n"
        return PlainTextResponse(body, media_type="text/plain; version=0.0.4; charset=utf-8")
    finally:
        try:
            con.close()
        except Exception:
            pass


@router.get("/characters")
def list_characters_route(request: Request = None, gender: str | None = None, limit: int = 50):
    """P3+ 路由: 返回 characters 列表, fliki picker shape [{_id, name, gender, looksCount, thumbnail}].

    - gender (query, 可选): 小写 / 大写都接受, 内部转大写匹配 characters.kind
    - limit 默认 50, 上限 200
    - 公开端点: 无 token 也能查 (跟 voices/gallery 一致)
    """
    return list_characters(gender=gender, limit=limit)


def list_characters(gender: str | None = None, limit: int = 50):
    """characters -> fliki picker shape. kind -> gender (upper); meta_json.looksCount -> looksCount; image_path -> thumbnail."""
    capped_limit = max(1, min(int(limit or 50), 200))
    con = get_db()
    try:
        where = ""
        params: list = []
        if gender:
            where = " WHERE UPPER(kind) = ?"
            params.append(gender.strip().upper())
        params.append(capped_limit)
        rows = con.execute("SELECT * FROM characters" + where + " ORDER BY created_at DESC LIMIT ?", params).fetchall()
        result = []
        for row in rows:
            looks_count = 0
            if row["meta_json"]:
                try:
                    meta = json.loads(row["meta_json"])
                    looks_count = int(meta.get("looksCount") or 0)
                except Exception:
                    looks_count = 0
            result.append({
                "_id": row["id"],
                "name": row["name"],
                "gender": (row["kind"] or "").upper(),
                "looksCount": looks_count,
                "thumbnail": row["image_path"] or "",
            })
        return result
    finally:
        con.close()


@router.get("/providers")
def list_providers():
    return DEFAULT_PROVIDERS

@router.get("/")
def root():
    return {"api": "fliki-clone", "version": app.version, "endpoints": [
        "/health", "/styles", "/media-samples",
        "/render.latest", "/render.create", "/providers"
    ]}

def _emit_tenant_metrics(con, out):
    """rev24 阶段 D D1-1: tenant 维度 (user_id md5 哈希分 4 桶, 确定性).

    users 表无 tenant_id 字段, 暂用 hash(user_id)[0] -> tenant_a/b/c/d 模拟多租户聚合,
    后续真做多租户时切到 users.tenant_id 直接读.
    """
    def _bucket(user_id):
        h = hashlib.md5(str(user_id).encode("utf-8")).hexdigest()
        n = int(h[0], 16) % 4
        return "tenant_" + ("a", "b", "c", "d")[n]

    # 1) render_jobs per tenant
    out.append("# HELP fliki_render_jobs_per_tenant_total Render jobs by tenant bucket (md5(user_id) % 4)")
    out.append("# TYPE fliki_render_jobs_per_tenant_total gauge")
    try:
        rows = con.execute(
            "SELECT user_id, status, COUNT(*) FROM render_jobs WHERE user_id IS NOT NULL GROUP BY user_id, status"
        ).fetchall()
        agg = {}
        for user_id, status, cnt in rows:
            b = _bucket(user_id)
            agg[(b, status or "unknown")] = agg.get((b, status or "unknown"), 0) + cnt
        for (b, status), cnt in sorted(agg.items()):
            out.append("fliki_render_jobs_per_tenant_total{tenant=\"" + b + "\", status=\"" + str(status) + "\"} " + str(cnt))
    except Exception as e:
        out.append("# render_jobs per tenant error: " + str(e))
    out.append("")

    # 2) workflow_runs per tenant
    out.append("# HELP fliki_workflow_runs_per_tenant_total Workflow runs by tenant bucket")
    out.append("# TYPE fliki_workflow_runs_per_tenant_total gauge")
    try:
        rows = con.execute(
            "SELECT user_id, status, COUNT(*) FROM workflow_runs WHERE user_id IS NOT NULL GROUP BY user_id, status"
        ).fetchall()
        agg = {}
        for user_id, status, cnt in rows:
            b = _bucket(user_id)
            agg[(b, status or "unknown")] = agg.get((b, status or "unknown"), 0) + cnt
        for (b, status), cnt in sorted(agg.items()):
            out.append("fliki_workflow_runs_per_tenant_total{tenant=\"" + b + "\", status=\"" + str(status) + "\"} " + str(cnt))
    except Exception as e:
        out.append("# workflow_runs per tenant error: " + str(e))
    out.append("")

    # 3) active users per tenant in last 24h
    out.append("# HELP fliki_active_users_24h_per_tenant Active users in last 24h by tenant bucket")
    out.append("# TYPE fliki_active_users_24h_per_tenant gauge")
    try:
        for src in ("render_jobs", "workflow_runs"):
            rows = con.execute(
                "SELECT DISTINCT user_id FROM " + src + " WHERE user_id IS NOT NULL AND created_at >= datetime('now', '-1 day')"
            ).fetchall()
            bucket_users = {"tenant_a": set(), "tenant_b": set(), "tenant_c": set(), "tenant_d": set()}
            for (u,) in rows:
                bucket_users[_bucket(u)].add(u)
            for b, users in sorted(bucket_users.items()):
                if users:
                    out.append("fliki_active_users_24h_per_tenant{tenant=\"" + b + "\", source=\"" + src + "\"} " + str(len(users)))
    except Exception as e:
        out.append("# active users per tenant error: " + str(e))
    out.append("")

