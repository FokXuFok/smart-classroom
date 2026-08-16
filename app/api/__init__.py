# -*- coding: utf-8 -*-
"""API 路由汇总（后续任务在此追加更多子路由）"""
from fastapi import APIRouter

from app.api import (
    admin,
    ai,
    auth,
    counselor,
    homework,
    interaction,
    notification,
    student,
    teacher,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(teacher.router)
api_router.include_router(student.router)
api_router.include_router(homework.router)
api_router.include_router(ai.router)
api_router.include_router(interaction.router)
api_router.include_router(counselor.router)
api_router.include_router(admin.router)
api_router.include_router(notification.router)
