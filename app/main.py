# -*- coding: utf-8 -*-
"""FastAPI 应用入口：API 路由优先，再挂载 /uploads 与前端静态页"""
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from app.api import api_router
from app.core.exception import register_exception_handlers
from app.core.logger import get_logger, new_req_id, req_id_var, setup_logging

# 日志必须最先初始化，后续所有模块的日志才能进入滚动文件
setup_logging()

app = FastAPI(title="全流程智慧课堂系统")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

access_log = get_logger("app.access")


@app.middleware("http")
async def request_context_middleware(request, call_next):
    """请求级 req_id + 访问日志（仅 /api/，静态资源不记）+ 禁缓存头"""
    req_id = new_req_id()
    token = req_id_var.set(req_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        # 所有响应禁止缓存：确保浏览器永远拿到最新文件，避免改了前端不生效
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["X-Request-ID"] = req_id
        if request.url.path.startswith("/api/"):
            duration = (time.perf_counter() - start) * 1000
            access_log.info(
                "%s %s -> %s %.1fms",
                request.method,
                request.url.path,
                response.status_code,
                duration,
            )
        return response
    except Exception:
        duration = (time.perf_counter() - start) * 1000
        access_log.exception(
            "%s %s 未捕获异常 %.1fms", request.method, request.url.path, duration
        )
        raise
    finally:
        req_id_var.reset(token)


register_exception_handlers(app)
app.include_router(api_router)

# 静态托管：必须位于 include_router 之后，保证 /api/** 优先匹配
# /uploads 已改为鉴权接口（app/api/files.py），不再公开托管；
# include_router 在前，/uploads/** 由鉴权路由接管，其余路径落到前端静态页

# 旧版 HTML 前端（web/）：根路径托管，登录后按角色跳转 *.html
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=config.BASE_DIR / "web", html=True), name="web")
