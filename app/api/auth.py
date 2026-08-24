# -*- coding: utf-8 -*-
"""认证路由：登录 / 登出 / 当前用户信息

token 存放在 httpOnly cookie（按角色命名 sc_token_<role>），会话级。
前端 JS 不可读，fetch 同源自动携带，杜绝 XSS 窃取与浏览器存储残留。
"""
import datetime

from fastapi import APIRouter, Depends, Request, Response

import config
from app.api.deps import ROLE_MODEL_PK, CurrentUser, get_current_user
from app.core.exception import BizError, ok
from app.core.security import create_token, revoke_token, verify_password
from app.database import get_db
from app.models import AuditLog, LoginAttempt
from app.schemas.auth import LoginReq

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOCK_THRESHOLD = 5      # 连续失败次数阈值
LOCK_MINUTES = 10       # 锁定时长（分钟）


@router.post("/login")
def login(req: LoginReq, request: Request, response: Response, db=Depends(get_db)):
    username = req.username.strip()
    now = datetime.datetime.now()

    # ---- 登录锁定检查（login_attempt 表）----
    attempt = (
        db.query(LoginAttempt).filter(LoginAttempt.username == username).first()
    )
    if attempt and attempt.lock_until and attempt.lock_until > now:
        raise BizError(1002, "失败次数过多，账号已锁定，请10分钟后再试")

    # ---- 按 role 查表 ----
    model, pk = ROLE_MODEL_PK[req.role]
    user = db.query(model).filter(getattr(model, pk) == username).first()
    if user is None:
        raise BizError(404, "账号不存在")
    if getattr(user, "status", 1) == 0:
        raise BizError(1003, "账号被禁用，请联系管理员")

    # ---- 密码校验 + 失败计数/锁定 ----
    if not verify_password(req.password, user.password or ""):
        if attempt is None:
            attempt = LoginAttempt(username=username, fail_count=0)
            db.add(attempt)
        attempt.fail_count = (attempt.fail_count or 0) + 1
        attempt.last_fail_time = now
        if attempt.fail_count >= LOCK_THRESHOLD:
            attempt.lock_until = now + datetime.timedelta(minutes=LOCK_MINUTES)
            attempt.fail_count = 0
        db.commit()
        raise BizError(1001, "用户名或密码错误")

    # ---- 登录成功：清理锁定 + 审计日志 ----
    if attempt is not None:
        db.delete(attempt)
    db.add(
        AuditLog(
            action="login",
            user_id=username,
            user_role=req.role,
            ip=request.client.host if request.client else None,
        )
    )
    db.commit()

    token = create_token(username, req.role, user.name, config.INSTANCE_ID)

    # token 写入 httpOnly 会话 cookie（按角色分名，四端互不覆盖）
    # 不设 max_age → 浏览器关闭即删除
    cookie_name = f"sc_token_{req.role}"
    response.set_cookie(
        cookie_name, token,
        path="/", samesite="lax", httponly=True,
    )

    return ok(
        {"role": req.role, "name": user.name, "user_id": username}
    )


@router.post("/logout")
def logout(current: CurrentUser = Depends(get_current_user), response: Response = None):
    """退出登录：吊销当前 token + 删除当前角色的 cookie"""
    # token 加入黑名单：即使 cookie 被浏览器恢复，旧 token 也无法使用
    revoke_token(current.jti, current.exp)
    if response:
        response.delete_cookie(f"sc_token_{current.role}", path="/")
    return ok()


@router.get("/me")
def me(current: CurrentUser = Depends(get_current_user)):
    """当前登录用户信息（前端页面加载时调用，401 则跳转登录页）"""
    user = current.user
    role = current.role
    data = {"user_id": getattr(user, _pk_attr(role)), "role": role, "name": user.name}
    return ok(data)


def _pk_attr(role: str) -> str:
    """role → 主键属性名"""
    return ROLE_MODEL_PK[role][1]
