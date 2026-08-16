# -*- coding: utf-8 -*-
"""FastAPI 应用入口：API 路由优先，再挂载 /uploads 与前端静态页"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from app.api import api_router
from app.core.exception import register_exception_handlers

app = FastAPI(title="全流程智慧课堂系统")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_middleware(request, call_next):
    """所有响应禁止缓存：确保浏览器永远拿到最新文件，避免改了前端不生效"""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


register_exception_handlers(app)
app.include_router(api_router)

# 静态托管：必须位于 include_router 之后，保证 /api/** 优先匹配
config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=config.BASE_DIR / "web", html=True), name="web")
