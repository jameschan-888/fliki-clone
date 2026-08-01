"""Simple JWT auth router (rev18 stage C 项 #6).

Endpoints:
  POST /auth/register   -> { email, password }          -> { token, refresh_token, user }
  POST /auth/login      -> { email, password }          -> { token, refresh_token, user }
  POST /auth/refresh    -> rotate refresh token          -> { token, refresh_token, user }
  POST /auth/logout     -> revoke refresh token
  GET  /auth/me         -> Bearer token               -> { user }
  GET  /auth/users      -> (admin only)               -> list of users

JWT_SECRET env (default 'fliki-dev-secret-CHANGE-IN-PROD').
Implements bcrypt-like password hashing via hashlib.pbkdf2_hmac (stdlib only).

Design: minimal but functional. Real production needs:
- bcrypt/argon2 instead of pbkdf2
- rate limiting on /login
- email verification flow
"""
import sys
import sqlite3
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from db.connection import get_db
def _resolve_con(con):
    """FastAPI injects con via Depends(get_db); direct calls (tests) pass Depends object.
    Detect & resolve to a real sqlite3.Connection by calling get_db() ourselves.
    Tests mock main.get_db (legacy pattern); fall back to it before going to db.connection.
    """
    if hasattr(con, "execute") and hasattr(con, "close"):
        return con
    try:
        import main as _main
        return _main.get_db()
    except Exception:
        from db.connection import get_db as _gdb
        return _gdb()
from rate_limit import SlidingWindowLimiter
from pydantic import BaseModel, EmailStr, Field

router = APIRouter(prefix="/auth", tags=["auth"])
_LOGIN_LIMITER = SlidingWindowLimiter(max_hits=5, window_seconds=60.0)
_REGISTER_LIMITER = SlidingWindowLimiter(max_hits=5, window_seconds=60.0)

def _client_ip(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"

def _enforce_rate_limit(limiter: SlidingWindowLimiter, key: str) -> None:
    blocked, _ = limiter.hit(key)
    if blocked:
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "RATE_LIMITED",
                "message": "请求过于频繁，请稍后再试",
                "hint": "Per-IP/email 5 requests/minute; 等待 1 分钟后重试",
            },
        )

JWT_SECRET = os.environ.get("FLIKI_JWT_SECRET", "fliki-dev-secret-CHANGE-IN-PROD")
JWT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


# ===== P2-Hardening: production must override JWT_SECRET =====
_DEFAULT_JWT_SECRET = "fliki-dev-secret-CHANGE-IN-PROD"


def validate_jwt_secret(strict):
    """启动时校验 JWT_SECRET. strict=True 强制占位符 raise, dev 默认警告.

    在 main.py 启动时调用:
      validate_jwt_secret(strict=(os.getenv("FLIKI_ENV") == "prod"))
    """
    env_value = os.environ.get("FLIKI_JWT_SECRET", _DEFAULT_JWT_SECRET)
    is_default = env_value == _DEFAULT_JWT_SECRET
    if is_default:
        placeholder = _DEFAULT_JWT_SECRET
        msg = "[auth_router] FLIKI_JWT_SECRET is still placeholder: " + placeholder + ". Set strong random string before FLIKI_ENV=prod."
        if strict:
            raise RuntimeError(msg)
        print(msg, file=sys.stderr)
    elif len(env_value) < 16:
        msg = "[auth_router] FLIKI_JWT_SECRET length only " + str(len(env_value)) + ", recommend >= 32 chars."
        if strict:
            raise RuntimeError(msg)
        print(msg, file=sys.stderr)

PBKDF2_ITERS = 600_000  # rev24 阶段 D P0: OWASP 2023 推荐 (原 100k 偏弱)
PBKDF2_ITERS_LEGACY = 100_000  # 兼容老 hash 验证


# rev24 阶段 D P0: PBKDF2 升级到 600k (OWASP 2023 推荐, 原 100k 偏弱).
# 兼容旧 hash: 老 hash 没 'iter:' 前缀, 用 PBKDF2_ITERS_LEGACY=100k 验.
# login 成功且 hash 是老格式时, 自动 rehash 用新 iter 并写回 db.
def _hash_pw(password: str, salt: str | None = None, iters: int | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    use_iters = iters if iters is not None else PBKDF2_ITERS
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), use_iters)
    return salt, f"{use_iters}:{h.hex()}"


def _verify_pw(password: str, salt: str, expected: str) -> bool:
    if ":" in expected:
        iters_str, hash_hex = expected.split(":", 1)
        use_iters = int(iters_str)
    else:
        # 老 hash: 100k iter
        use_iters = PBKDF2_ITERS_LEGACY
        hash_hex = expected
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), use_iters)
    return hmac.compare_digest(h.hex(), hash_hex)




REFRESH_TOKEN_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


def _make_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, token_hash


def _hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _store_refresh_token(con, user_id, token_hash, ttl_seconds):
    now = int(time.time())
    expires = now + ttl_seconds
    con.execute(
        "INSERT INTO refresh_tokens (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, expires, now),
    )
    con.commit()
    return expires


def _revoke_refresh_token(con, token_hash, replaced_by=None):
    now = int(time.time())
    if replaced_by:
        sql = "UPDATE refresh_tokens SET revoked_at=?, replaced_by_id=? WHERE id=? AND revoked_at IS NULL"
        params = (now, replaced_by, token_hash)
    else:
        sql = "UPDATE refresh_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL"
        params = (now, token_hash)
    cursor = con.execute(sql, params)
    con.commit()
    return cursor.rowcount == 1


def _find_refresh_token(con, token_hash):
    return con.execute(
        "SELECT user_id, expires_at, revoked_at, replaced_by_id FROM refresh_tokens WHERE id=?",
        (token_hash,),
    ).fetchone()


def _revoke_refresh_descendants(con, first_hash, revoked_at):
    current_hash = first_hash
    visited = set()
    revoked_count = 0
    while current_hash and current_hash not in visited:
        visited.add(current_hash)
        row = con.execute(
            "SELECT replaced_by_id FROM refresh_tokens WHERE id=?",
            (current_hash,),
        ).fetchone()
        if row is None:
            break
        cursor = con.execute(
            "UPDATE refresh_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
            (revoked_at, current_hash),
        )
        revoked_count += max(cursor.rowcount, 0)
        current_hash = row[0]
    return revoked_count


def _rotate_refresh_token(con, raw_token):
    token_hash = _hash_refresh_token(raw_token)
    now = int(time.time())
    try:
        con.execute("BEGIN IMMEDIATE")
        row = _find_refresh_token(con, token_hash)
        if row is None:
            raise HTTPException(
                status_code=401,
                detail={"error_code": "REFRESH_INVALID", "message": "刷新凭证无效，请重新登录"},
            )

        user_id, expires_at, revoked_at, replaced_by_id = row
        if revoked_at is not None:
            if replaced_by_id:
                _revoke_refresh_descendants(con, replaced_by_id, now)
                con.commit()
                raise HTTPException(
                    status_code=401,
                    detail={
                        "error_code": "REFRESH_REUSED",
                        "message": "检测到刷新凭证被重复使用，当前会话已撤销，请重新登录",
                    },
                )
            raise HTTPException(
                status_code=401,
                detail={"error_code": "REFRESH_REVOKED", "message": "刷新凭证已撤销，请重新登录"},
            )
        if expires_at <= now:
            con.execute(
                "UPDATE refresh_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (now, token_hash),
            )
            con.commit()
            raise HTTPException(
                status_code=401,
                detail={"error_code": "REFRESH_EXPIRED", "message": "登录已过期，请重新登录"},
            )

        user_row = con.execute(
            "SELECT id, email, role FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        if user_row is None:
            con.execute(
                "UPDATE refresh_tokens SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
                (now, token_hash),
            )
            con.commit()
            raise HTTPException(
                status_code=401,
                detail={"error_code": "USER_NOT_FOUND", "message": "用户不存在，请重新登录"},
            )

        new_raw_token, new_token_hash = _make_refresh_token()
        new_expires_at = now + REFRESH_TOKEN_TTL_SECONDS
        cursor = con.execute(
            "UPDATE refresh_tokens SET revoked_at=?, replaced_by_id=? WHERE id=? AND revoked_at IS NULL",
            (now, new_token_hash, token_hash),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("refresh token rotation lost ownership")
        con.execute(
            "INSERT INTO refresh_tokens (id, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (new_token_hash, user_id, new_expires_at, now),
        )
        con.commit()
        role = user_row[2] or "user"
        return {
            "token": _make_token(user_id, role),
            "refresh_token": new_raw_token,
            "refresh_expires_at": new_expires_at,
            "user": {"id": user_id, "email": user_row[1], "role": role},
        }
    except Exception:
        try:
            con.rollback()
        except Exception:
            pass
        raise


def _make_token(user_id: str, role: str) -> str:
    header = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
    payload = json.dumps({
        "sub": user_id,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_TTL_SECONDS,
    }, separators=(",", ":")).encode()
    h64 = _b64u(header)
    p64 = _b64u(payload)
    sig = hmac.new(JWT_SECRET.encode(), f"{h64}.{p64}".encode(), hashlib.sha256).digest()
    sig64 = _b64u_bytes(sig)
    return f"{h64}.{p64}.{sig64}"


def _b64u(s: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(s).rstrip(b"=").decode("ascii")


def _b64u_bytes(s: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(s).rstrip(b"=").decode("ascii")


def _decode_token(token: str) -> dict | None:
    try:
        h64, p64, sig64 = token.split(".")
        import base64
        h = base64.urlsafe_b64decode(h64 + "==")
        p = base64.urlsafe_b64decode(p64 + "==")
        sig = base64.urlsafe_b64decode(sig64 + "==")
        expected = hmac.new(JWT_SECRET.encode(), f"{h64}.{p64}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(p)
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None



def _decode_token_lenient(token, max_age_seconds=60 * 60 * 24 * 30):
    # 签名验证 + exp 在 max_age_seconds 内的过期 token. 用于 /auth/refresh 续期.
    try:
        h64, p64, sig64 = token.split('.')
        import base64
        h = base64.urlsafe_b64decode(h64 + '==')
        p = base64.urlsafe_b64decode(p64 + '==')
        sig = base64.urlsafe_b64decode(sig64 + '==')
        expected = hmac.new(JWT_SECRET.encode(), f'{h64}.{p64}'.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(p)
        now = int(time.time())
        if payload.get('exp', 0) > now:
            return payload
        if now - payload.get('exp', 0) > max_age_seconds:
            return None
        return payload
    except Exception:
        return None

def get_user_id_from_request(request) -> str | None:
    # request may be None when called outside a FastAPI route (e.g. unit tests
    # that invoke the underlying function directly). Be defensive.
    if request is None:
        return None
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = _decode_token(auth[7:])
    return payload.get("sub") if payload else None


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    role: str = Field(default="user", pattern="^(user|admin)$")


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterBody, request: Request, con: sqlite3.Connection = Depends(get_db)):
    con = _resolve_con(con)
    # rev35: 端点限速前置 (角色白名单前, 避免 403/409/429 探测区分).
    _enforce_rate_limit(_REGISTER_LIMITER, _client_ip(request) + "|" + body.email.lower().strip())
    _enforce_rate_limit(_REGISTER_LIMITER, _client_ip(request))
    if body.role != "user":
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "ADMIN_REGISTRATION_DISABLED",
                "message": "公开注册不能创建管理员账号",
            },
        )
    try:
        normalized_email = body.email.lower().strip()
        existing = con.execute("SELECT id FROM users WHERE email=?", (normalized_email,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail={"error_code": "EMAIL_EXISTS", "message": "邮箱已注册", "hint": "改用 /auth/login"})
        user_id = uuid.uuid4().hex
        salt, pw_hash = _hash_pw(body.password)
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        con.execute(
            "INSERT INTO users (id, email, password_salt, password_hash, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, normalized_email, salt, pw_hash, "user", now, now),
        )
        con.commit()
        token = _make_token(user_id, "user")
        raw_rt, hash_rt = _make_refresh_token()
        rt_expires = _store_refresh_token(con, user_id, hash_rt, REFRESH_TOKEN_TTL_SECONDS)
        return {"token": token, "refresh_token": raw_rt, "refresh_expires_at": rt_expires, "user": {"id": user_id, "email": normalized_email, "role": "user"}}
    finally:
        con.close()


@router.post("/login")
def login(body: LoginBody, request: Request, con: sqlite3.Connection = Depends(get_db)):
    con = _resolve_con(con)
    _enforce_rate_limit(_LOGIN_LIMITER, _client_ip(request) + "|" + body.email.lower().strip())
    _enforce_rate_limit(_LOGIN_LIMITER, _client_ip(request))
    try:
        row = con.execute("SELECT id, email, password_salt, password_hash, role FROM users WHERE email=?", (body.email.lower().strip(),)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail={"error_code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误", "hint": "检查 email/password"})
        if not _verify_pw(body.password, row[2], row[3]):
            raise HTTPException(status_code=401, detail={"error_code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误", "hint": "检查 email/password"})
        # rev24 阶段 D P0: 老 hash (100k iter, 无 'iter:' 前缀) 登录后自动 rehash 到 600k
        if ":" not in row[3]:
            _, new_hash = _hash_pw(body.password, row[2])  # 复用原 salt
            con.execute("UPDATE users SET password_hash=?, updated_at=? WHERE id=?",
                        (new_hash, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), row[0]))
            con.commit()
        token = _make_token(row[0], row[4])
        # rev34: 同步签 refresh token.
        raw_rt, hash_rt = _make_refresh_token()
        rt_expires = _store_refresh_token(con, row[0], hash_rt, REFRESH_TOKEN_TTL_SECONDS)
        return {"token": token, "refresh_token": raw_rt, "refresh_expires_at": rt_expires, "user": {"id": row[0], "email": row[1], "role": row[4]}}
    finally:
        con.close()


@router.get("/me")
def me(request: Request, con: sqlite3.Connection = Depends(get_db)):
    con = _resolve_con(con)
    uid = get_user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "missing/invalid token"})
    try:
        row = con.execute("SELECT id, email, role, created_at FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail={"error_code": "USER_NOT_FOUND"})
        return {"user": {"id": row[0], "email": row[1], "role": row[2], "created_at": row[3]}}
    finally:
        con.close()



class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=512)


@router.post("/refresh")
def refresh(request: Request, body: RefreshBody | None = None, con: sqlite3.Connection = Depends(get_db)):
    con = _resolve_con(con)
    # rev34 P1: 优先 body.refresh_token (rotation), 否则 Authorization Bearer access_token (rev33 P1-B grace).
    try:
        if body and body.refresh_token:
            return _rotate_refresh_token(con, body.refresh_token)

        # === access token grace path (rev33 P1-B 向后兼容) ===
        if request is None:
            raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "missing token"})
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN", "message": "missing bearer token"})
        payload = _decode_token_lenient(auth[7:])
        if not payload:
            raise HTTPException(status_code=401, detail={"error_code": "TOKEN_EXPIRED", "message": "token expired or invalid, please re-login"})
        sub = payload.get("sub")
        if not sub:
            raise HTTPException(status_code=401, detail={"error_code": "INVALID_TOKEN", "message": "missing sub in token"})
        user_row = con.execute("SELECT id, email, role FROM users WHERE id=?", (sub,)).fetchone()
        if not user_row:
            raise HTTPException(status_code=401, detail={"error_code": "USER_NOT_FOUND", "message": "user no longer exists"})
        role = user_row[2] or "user"
        new_token = _make_token(user_row[0], role)
        return {"token": new_token, "user": {"id": user_row[0], "email": user_row[1], "role": role}}
    finally:
        con.close()



class LogoutBody(BaseModel):
    refresh_token: str = Field(min_length=16, max_length=512)


@router.post("/logout")
def logout(body: LogoutBody, con: sqlite3.Connection = Depends(get_db)):
    con = _resolve_con(con)
    # rev34 P1: 撤销 refresh_token (单设备退出). 失败返回 204 (幂等).
    try:
        hash_id = _hash_refresh_token(body.refresh_token)
        _revoke_refresh_token(con, hash_id)
        return {"revoked": True}
    finally:
        con.close()

@router.get("/users")
def list_users(request: Request, con: sqlite3.Connection = Depends(get_db)):
    con = _resolve_con(con)
    uid = get_user_id_from_request(request)
    if not uid:
        raise HTTPException(status_code=401, detail={"error_code": "MISSING_TOKEN"})
    try:
        actor = con.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
        if not actor or actor[0] != "admin":
            raise HTTPException(status_code=403, detail={"error_code": "ADMIN_ONLY", "message": "需要 admin 权限"})
        rows = con.execute("SELECT id, email, role, created_at FROM users ORDER BY created_at DESC LIMIT 100").fetchall()
        return {"users": [{"id": r[0], "email": r[1], "role": r[2], "created_at": r[3]} for r in rows]}
    finally:
        con.close()


# DB schema (idempotent create on import)
def ensure_users_table(con=None):
    own = con is None
    if own:
        from db.connection import get_db
        con = get_db()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        con.commit()
        # rev34 P1: refresh_tokens 表 (rotation 撤销列表)
        con.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                revoked_at INTEGER,
                replaced_by_id TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id, created_at DESC)")
        con.commit()
    finally:
        if own:
            con.close()
