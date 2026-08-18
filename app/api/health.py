# -*- coding: utf-8 -*-
"""健康检查：服务存活 + 数据库连通性（无需登录，换机部署时一眼判断状态）"""
import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.exception import ok
from app.database import engine

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health():
    db_ok = True
    error = None
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        error = f"{type(exc).__name__}: {exc}"[:200]
    return ok(
        {
            "status": "ok" if db_ok else "degraded",
            "db": db_ok,
            "db_latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": error,
        }
    )
