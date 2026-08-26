# -*- coding: utf-8 -*-
"""认证路由：登录 / 登出 / 注册 / 当前用户信息

token 存放在 httpOnly cookie（统一命名 sc_token），会话级。
登录不指定角色，后端根据账号自动判断身份（四张用户表逐个查找）。
前端 JS 不可读，fetch 同源自动携带，杜绝 XSS 窃取与浏览器存储残留。
"""
import datetime

from fastapi import APIRouter, Depends, Request, Response

import config
from app.api.deps import ROLE_MODEL_PK, CurrentUser, get_current_user
from app.core.exception import BizError, ok
from app.core.security import (
    create_token,
    hash_password,
    revoke_token,
    verify_password,
)
from app.database import get_db
from app.models import AuditLog, ClassInfo, LoginAttempt, Student, Teacher
from app.schemas.auth import LoginReq, RegisterReq

router = APIRouter(prefix="/api/auth", tags=["auth"])

LOCK_THRESHOLD = 5      # 连续失败次数阈值
LOCK_MINUTES = 10       # 锁定时长（分钟）


def _find_user(db, username: str):
    """按账号在四张用户表中查找，返回 (user, role)；找不到返回 (None, None)"""
    for role, (model, pk) in ROLE_MODEL_PK.items():
        user = db.query(model).filter(getattr(model, pk) == username).first()
        if user is not None:
            return user, role
    return None, None


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

    # ---- 自动判断身份：四表逐个查找 ----
    user, role = _find_user(db, username)
    if user is None:
        raise BizError(404, "账号不存在")
    status = getattr(user, "status", 1)
    if status == 2:
        raise BizError(1003, "账号待审批，请联系管理员")
    if status == 0:
        raise BizError(1003, "账号已禁用，请联系管理员")

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
            user_role=role,
            ip=request.client.host if request.client else None,
        )
    )
    db.commit()

    token = create_token(username, role, user.name, config.INSTANCE_ID)

    # token 写入 httpOnly 会话 cookie（统一命名 sc_token，登录新账号直接覆盖）
    # 不设 max_age → 浏览器关闭即删除
    response.set_cookie(
        "sc_token", token,
        path="/", samesite="lax", httponly=True,
    )

    return ok(
        {"role": role, "name": user.name, "user_id": username}
    )


@router.post("/logout")
def logout(current: CurrentUser = Depends(get_current_user), response: Response = None):
    """退出登录：吊销当前 token + 删除 cookie"""
    # token 加入黑名单：即使 cookie 被浏览器恢复，旧 token 也无法使用
    revoke_token(current.jti, current.exp)
    if response:
        response.delete_cookie("sc_token", path="/")
        # 清理旧版按角色命名遗留的 cookie（sc_token_*），避免历史残留干扰
        for role in ("student", "teacher", "counselor", "admin"):
            response.delete_cookie(f"sc_token_{role}", path="/")
    return ok()


@router.get("/me")
def me(current: CurrentUser = Depends(get_current_user)):
    """当前登录用户信息（前端页面加载时调用，401 则跳转登录页）"""
    user = current.user
    role = current.role
    data = {"user_id": getattr(user, _pk_attr(role)), "role": role, "name": user.name}
    return ok(data)


@router.post("/register")
def register(req: RegisterReq, db=Depends(get_db)):
    """自助注册：学生 / 教师，status=0 待管理员审批"""
    username = req.username.strip()
    if not username:
        raise BizError(400, "账号不能为空")
    if len(username) > 20:
        raise BizError(400, "账号长度不能超过 20 位")
    if not req.name or not req.name.strip():
        raise BizError(400, "姓名不能为空")
    if len(req.password or "") < 6:
        raise BizError(400, "密码至少 6 位")

    # 账号已存在（四表任意命中）
    existing, _ = _find_user(db, username)
    if existing is not None:
        raise BizError(400, "该账号已存在")

    if req.role == "student":
        if not req.class_id:
            raise BizError(400, "学生必须选择班级")
        if (
            db.query(ClassInfo)
            .filter(ClassInfo.class_code == req.class_id)
            .first()
            is None
        ):
            raise BizError(404, "班级不存在")
        user = Student(
            student_no=username,
            name=req.name.strip(),
            class_id=req.class_id,
            password=hash_password(req.password),
        )
    else:  # teacher
        user = Teacher(
            teacher_no=username,
            name=req.name.strip(),
            password=hash_password(req.password),
        )
    user.status = 2  # 待审批
    db.add(user)
    db.commit()
    return ok(
        {"user_id": username, "role": req.role},
        message="注册成功，请等待管理员审核通过后登录",
    )


@router.get("/class-options")
def class_options(db=Depends(get_db)):
    """公开班级列表（注册页下拉选择）"""
    rows = (
        db.query(ClassInfo.class_code, ClassInfo.class_name)
        .order_by(ClassInfo.class_code)
        .all()
    )
    return ok([{"class_code": c, "class_name": n} for c, n in rows])


def _pk_attr(role: str) -> str:
    """role → 主键属性名"""
    return ROLE_MODEL_PK[role][1]
