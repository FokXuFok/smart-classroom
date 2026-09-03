# -*- coding: utf-8 -*-
"""FastAPI 依赖：当前登录用户（从 httpOnly cookie 读取 token）

多角色共存：每个角色独立 cookie（sc_token_student / sc_token_teacher /
sc_token_counselor / sc_token_admin），同一浏览器可同时登录多个角色——
学生标签与教师标签各持各的 cookie，刷新互不影响，实现"同时在线"。
require_roles(角色) 精确匹配对应角色 cookie；get_current_user（任意角色）
依赖前端 X-Role 请求头指定角色，未指定时按各角色 cookie 兜底（兼容
<img src> 等无法携带请求头的静态资源加载）。
"""
from collections import namedtuple
from typing import Optional

import jwt
from fastapi import Depends, Header, Request

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

# 各角色 cookie 名：sc_token_{role}
ROLES = tuple(ROLE_MODEL_PK.keys())


def _extract_token(request: Request, role: Optional[str] = None) -> Optional[str]:
    """从 httpOnly cookie 读取 token

    role 指定：只读 sc_token_{role}（精确匹配，杜绝跨角色串号）；
    role 未指定：依次尝试各角色 cookie + 旧版统一 sc_token + Authorization 头。
    """
    if role:
        val = request.cookies.get(f"sc_token_{role}")
        if val:
            return val
        return None
    for r in ROLES:
        val = request.cookies.get(f"sc_token_{r}")
        if val:
            return val
    # 兼容旧版统一 cookie 与 Authorization: Bearer
    val = request.cookies.get("sc_token")
    if val:
        return val
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None


def _resolve_current(token: str, db) -> Optional[CurrentUser]:
    """解码 + 校验 + 查表 → CurrentUser；token 无效返回 None（账号禁用抛 403）"""
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

    # 校验 instance_id：后端重启后旧 token 失效
    # （对抗浏览器"恢复上次会话"——会话 cookie 被恢复但 instance_id 不匹配）
    if payload.get("instance_id") != config.INSTANCE_ID:
        return None

    # 校验黑名单：登出后的 token 立即失效
    jti = payload.get("jti")
    if not jti or is_token_revoked(jti):
        return None

    # 按 role 查表
    role = payload.get("role")
    user_id = payload.get("sub")
    if role not in ROLE_MODEL_PK or not user_id:
        return None
    model, pk = ROLE_MODEL_PK[role]
    user = db.query(model).filter(getattr(model, pk) == user_id).first()

    # 查无此人 / 账号被禁用或待审批
    if user is None:
        return None
    if getattr(user, "status", 1) != 1:
        raise BizError(403, "账号不可用（待审批或已禁用）")

    return CurrentUser(user=user, role=role, jti=jti, exp=payload.get("exp"))


def get_current_user(
    request: Request,
    db=Depends(get_db),
    role: Optional[str] = Header(default=None, alias="X-Role"),
) -> CurrentUser:
    """任意角色当前用户。role 请求头指定时精确匹配对应角色 cookie。

    前端 api.js 统一携带 X-Role（如 student/teacher），使 /me、通知列表等
    "不限定角色"的接口能正确解析出是哪个角色在调用。
    """
    token = _extract_token(request, role)
    if not token:
        raise BizError(401, "未登录或登录已过期")
    current = _resolve_current(token, db)
    if current is None:
        raise BizError(401, "未登录或登录已过期")
    return current


def require_roles(*roles):
    """依赖工厂：按角色 cookie 精确认证。

    依次尝试各期望角色的 cookie，命中有效 token 即返回该身份；
    全部未命中 → 401（该角色未登录）；角色不符 → 403。
    """
    def checker(request: Request, db=Depends(get_db)) -> CurrentUser:
        for r in roles:
            token = _extract_token(request, r)
            if not token:
                continue
            current = _resolve_current(token, db)
            if current is None:
                continue
            return current
        # 账号禁用等确定性错误由 _resolve_current 抛 403，走到这里即"该角色未登录"
        raise BizError(401, "未登录或登录已过期")

    return checker
