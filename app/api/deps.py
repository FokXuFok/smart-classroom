# -*- coding: utf-8 -*-
"""FastAPI 依赖：当前登录用户（从 httpOnly cookie 读取 token）"""
from collections import namedtuple
from typing import Optional

import jwt
from fastapi import Depends, Request

import config
from app.core.exception import BizError
from app.core.security import decode_token, is_token_revoked
from app.database import get_db  # noqa: F401  直接 re-export
from app.models import Admin, Counselor, Student, Teacher

CurrentUser = namedtuple("CurrentUser", ["user", "role", "jti", "exp"])

# role → (ORM 类, 主键字段名)
ROLE_MODEL_PK = {
    "student": (Student, "student_no"),
    "teacher": (Teacher, "teacher_no"),
    "counselor": (Counselor, "counselor_no"),
    "admin": (Admin, "admin_no"),
}


def _extract_token(request: Request) -> Optional[str]:
    """从 httpOnly cookie 读取 token（按角色遍历），兼容旧版 Authorization 头"""
    for role_name in ROLE_MODEL_PK:
        val = request.cookies.get(f"sc_token_{role_name}")
        if val:
            return val
    # 兼容旧版 Authorization: Bearer xxx
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def get_current_user(
    request: Request, db=Depends(get_db)
) -> CurrentUser:
    token = _extract_token(request)
    if not token:
        raise BizError(401, "未登录或登录已过期")

    # 解码 JWT
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise BizError(401, "登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise BizError(401, "未登录或登录已过期")

    # 校验 instance_id：后端重启后旧 token 失效
    # （对抗浏览器"恢复上次会话"——会话 cookie 被恢复但 instance_id 不匹配）
    if payload.get("instance_id") != config.INSTANCE_ID:
        raise BizError(401, "登录已过期，请重新登录")

    # 校验黑名单：登出后的 token 立即失效
    jti = payload.get("jti")
    if not jti or is_token_revoked(jti):
        raise BizError(401, "登录已失效，请重新登录")

    # 按 role 查表
    role = payload.get("role")
    user_id = payload.get("sub")
    if role not in ROLE_MODEL_PK or not user_id:
        raise BizError(401, "未登录或登录已过期")
    model, pk = ROLE_MODEL_PK[role]
    user = db.query(model).filter(getattr(model, pk) == user_id).first()

    # 查无此人 / 账号被禁用
    if user is None:
        raise BizError(401, "未登录或登录已过期")
    if getattr(user, "status", 1) == 0:
        raise BizError(403, "账号被禁用")

    return CurrentUser(user=user, role=role, jti=jti, exp=payload.get("exp"))


def require_roles(*roles):
    """依赖工厂：角色不匹配 → BizError(403,"无权限访问")；用法 Depends(require_roles("teacher"))"""

    def checker(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.role not in roles:
            raise BizError(403, "无权限访问")
        return current

    return checker
