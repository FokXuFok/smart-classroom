# -*- coding: utf-8 -*-
"""API 路由汇总（后续任务在此追加更多子路由）"""
from fastapi import APIRouter

from app.api import (
    admin,
    ai,
    auth,
    counselor,
    files,
    health,
    homework,
    interaction,
    notification,
    student,
    teacher,
)

api_router = APIRouter()
# /uploads/** 必须先于根静态挂载注册，由鉴权接口接管（替代原公开 StaticFiles）
api_router.include_router(files.router)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(teacher.router)
api_router.include_router(student.router)
api_router.include_router(homework.router)
api_router.include_router(ai.router)
api_router.include_router(interaction.router)
api_router.include_router(counselor.router)
api_router.include_router(admin.router)
api_router.include_router(notification.router)
