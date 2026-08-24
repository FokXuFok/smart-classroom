# -*- coding: utf-8 -*-
"""上传文件鉴权访问：/uploads/** 需登录才能读取

原 StaticFiles 公开托管任何人可按学号猜 URL 拖走人脸照片，
现改为带登录校验的文件接口（路径不变，前端与库中存的 URL 零改动）。
浏览器对同源请求自动携带 httpOnly cookie，<img> 标签同样适用。
"""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

import config
from app.api.deps import CurrentUser, get_current_user
from app.core.exception import BizError

router = APIRouter(prefix="/uploads", tags=["files"])


@router.get("/{path:path}")
def serve_upload(path: str, current: CurrentUser = Depends(get_current_user)):
    """读取上传目录内文件；未登录 401，路径越界/不存在 404"""
    # 防目录穿越：resolve 后必须仍位于上传目录内（拦 /uploads/../.env 等）
    upload_root = config.UPLOAD_DIR.resolve()
    file = (config.UPLOAD_DIR / path).resolve()
    if not file.is_relative_to(upload_root) or not file.is_file():
        raise BizError(404, "文件不存在")
    return FileResponse(file)
