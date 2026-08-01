"""rev35 阶段 2 P0.1: db 模块入口. 暴露 get_db / init_db 给 routers/* + main.py.
函数签名与原 main.py 版本一致 (保持下游依赖兼容), 后续 P2.10 阶段再迁 Depends(get_db).
"""
from db.connection import get_db, init_db  # noqa: F401
