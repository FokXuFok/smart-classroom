# -*- coding: utf-8 -*-
"""安全层 + 登录认证测试（打真实库）"""
import datetime

import jwt
import pytest
from fastapi.testclient import TestClient

import config
from app.api.files import serve_upload
from app.core.exception import BizError
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database import SessionLocal
from app.main import app
from app.models import LoginAttempt, Student, Teacher

client = TestClient(app)

USERNAME = "2024001"


@pytest.fixture()
def cleanup_lock():
    """测试结束后必须解锁：删除 login_attempt 对应行"""
    yield
    db = SessionLocal()
    try:
        db.query(LoginAttempt).filter(LoginAttempt.username == USERNAME).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def cleanup_reg_users():
    """注册流程测试后清理：删除注册产生的人员行"""
    yield
    db = SessionLocal()
    try:
        for model, pk, no in [(Student, "student_no", "R2026001"),
                              (Teacher, "teacher_no", "R9999")]:
            db.query(model).filter(getattr(model, pk) == no).delete()
        db.commit()
    finally:
        db.close()


# ---------- 密码哈希 ----------

def test_hash_and_verify_password():
    hashed = hash_password("123456")
    assert isinstance(hashed, str)
    assert hashed != "123456"
    assert verify_password("123456", hashed) is True
    assert verify_password("wrong-password", hashed) is False
    # 乱码哈希：返回 False 而非抛错
    assert verify_password("123456", "not-a-bcrypt-hash") is False
    assert verify_password("123456", "") is False


# ---------- JWT ----------

def test_token_roundtrip():
    token = create_token(USERNAME, "student", "张三")
    payload = decode_token(token)
    assert payload["sub"] == USERNAME
    assert payload["role"] == "student"
    assert payload["name"] == "张三"

    # 手动构造过期 token
    expired = jwt.encode(
        {
            "sub": USERNAME,
            "role": "student",
            "name": "张三",
            "exp": datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=1),
        },
        config.SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired)

    # 非法 token → InvalidTokenError（含 ExpiredSignatureError 之外的场景）
    with pytest.raises(jwt.InvalidTokenError):
        decode_token("garbage.token.value")


# ---------- 登录 / /me ----------

def test_login_success():
    # 登录走一次性 client，避免污染本模块共享 client 的 cookie jar
    c = TestClient(app)
    resp = c.post(
        "/api/auth/login",
        json={"username": USERNAME, "password": "123456"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    # token 现经 httpOnly cookie 下发（统一命名 sc_token），响应体不再含 token 字段
    cookie = resp.cookies.get("sc_token")
    assert cookie, "登录响应未下发 sc_token cookie"
    assert body["data"]["role"] == "student"
    assert body["data"]["user_id"] == USERNAME

    me = client.get("/api/auth/me", cookies={"sc_token": cookie})
    me_body = me.json()
    assert me_body["code"] == 0
    assert me_body["data"]["name"] == "张三"
    assert me_body["data"]["role"] == "student"
    assert me_body["data"]["user_id"] == USERNAME


def test_login_auto_detect_role():
    """不指定角色，后端按账号自动判断身份"""
    for username, password, role in [("2024001", "123456", "student"),
                                     ("T001", "123456", "teacher"),
                                     ("C001", "123456", "counselor"),
                                     ("admin", "admin123", "admin")]:
        resp = TestClient(app).post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )
        body = resp.json()
        assert body["code"] == 0, body
        assert body["data"]["role"] == role, f"{username} 身份判断错误"


def test_login_unified_cookie_no_cross_account():
    """串号根因回归：登录 A 后再登录 B，cookie 统一为 sc_token 并被覆盖，
    绝不会残留多个角色 cookie 导致取错身份"""
    c = TestClient(app)
    # 先登录学生，再登录教师 → 同一 cookie 名被覆盖
    c.post("/api/auth/login", json={"username": USERNAME, "password": "123456"})
    first = c.cookies.get("sc_token")
    assert first
    c.post("/api/auth/login", json={"username": "T001", "password": "123456"})
    assert c.cookies.get("sc_token") != first
    # 当前身份必须是教师（而非最开始的账号）
    me = c.get("/api/auth/me").json()
    assert me["code"] == 0
    assert me["data"]["user_id"] == "T001"
    assert me["data"]["role"] == "teacher"


# ---------- 注册 → 管理员审批 → 登录 ----------

def _reg_student(c, username="R2026001", password="abc123"):
    """注册学生（班级 CLS001），返回响应体"""
    resp = c.post("/api/auth/register", json={
        "username": username, "password": password, "name": "注册学生",
        "role": "student", "class_id": "CLS001",
    })
    return resp.json()


def test_register_student_pending_approval(cleanup_reg_users):
    c = TestClient(app)
    body = _reg_student(c)
    assert body["code"] == 0, body
    assert "待管理员审核" in body["message"]

    # 注册即创建 status=2（待审批）
    db = SessionLocal()
    try:
        row = db.query(Student).filter(Student.student_no == "R2026001").first()
        assert row is not None
        assert row.status == 2
    finally:
        db.close()

    # 待审批账号不能登录
    resp = c.post("/api/auth/login", json={"username": "R2026001", "password": "abc123"})
    assert resp.json()["code"] == 1003
    assert "待审批" in resp.json()["message"]

    # 重复注册 → 400
    assert _reg_student(c)["code"] == 400

    # 班级不存在 → 404
    resp = c.post("/api/auth/register", json={
        "username": "R2026002", "password": "abc123", "name": "无班生",
        "role": "student", "class_id": "NOPE",
    })
    assert resp.json()["code"] == 404


def test_register_teacher_and_class_options(cleanup_reg_users):
    c = TestClient(app)
    resp = c.post("/api/auth/register", json={
        "username": "R9999", "password": "abc123", "name": "注册教师",
        "role": "teacher",
    })
    assert resp.json()["code"] == 0, resp.json()

    db = SessionLocal()
    try:
        row = db.query(Teacher).filter(Teacher.teacher_no == "R9999").first()
        assert row is not None and row.status == 2
    finally:
        db.close()

    # 班级列表公开可读（注册页下拉）
    resp = c.get("/api/auth/class-options")
    body = resp.json()
    assert body["code"] == 0
    codes = {x["class_code"] for x in body["data"]}
    assert "CLS001" in codes


def test_admin_approve_registered_user(cleanup_reg_users):
    c = TestClient(app)
    _reg_student(c)

    # 管理员登录 → 列表可见待审批账号
    admin = TestClient(app)
    resp = admin.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.json()["code"] == 0, resp.json()
    admin_cookies = {"sc_token": resp.cookies.get("sc_token")}

    resp = client.get(
        "/api/admin/users", params={"role": "student", "keyword": "R2026001"},
        cookies=admin_cookies,
    )
    body = resp.json()
    assert body["code"] == 0
    item = next(u for u in body["data"]["items"] if u["user_id"] == "R2026001")
    assert item["status"] == 2

    # 审批通过（toggle-status：2 → 1）
    resp = client.post(
        "/api/admin/users/student/R2026001/toggle-status", cookies=admin_cookies
    )
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == 1

    # 审批通过后可正常登录并访问
    login = TestClient(app)
    resp = login.post("/api/auth/login", json={"username": "R2026001", "password": "abc123"})
    assert resp.json()["code"] == 0, resp.json()
    me = login.get("/api/auth/me").json()
    assert me["code"] == 0 and me["data"]["role"] == "student"


def test_me_without_token():
    client.cookies.clear()  # 确保无残留登录 cookie
    resp = client.get("/api/auth/me")
    body = resp.json()
    assert body["code"] == 401


# ---------- 登录失败锁定 ----------

def test_login_wrong_password_locked(cleanup_lock):
    # 连续错 5 次：每次都是 1001
    for _ in range(5):
        resp = client.post(
            "/api/auth/login",
            json={"username": USERNAME, "password": "wrong-pass"},
        )
        assert resp.json()["code"] == 1001

    # 第 6 次（即使密码正确）也被锁定拦截：1002
    resp = client.post(
        "/api/auth/login",
        json={"username": USERNAME, "password": "123456"},
    )
    assert resp.json()["code"] == 1002


# ---------- 登出黑名单：旧 token 立即失效 ----------

def test_logout_revokes_token():
    c = TestClient(app)
    c.post(
        "/api/auth/login",
        json={"username": USERNAME, "password": "123456"},
    )
    # 登出前可用
    assert c.get("/api/auth/me").json()["code"] == 0
    # 登出
    assert c.post("/api/auth/logout").json()["code"] == 0
    # 旧 token（即使 cookie 被恢复）已入黑名单 → 401
    resp = client.get(
        "/api/auth/me", cookies={"sc_token": c.cookies.get("sc_token")}
    )
    assert resp.json()["code"] == 401


def test_revoked_blacklist_unit():
    """黑名单单元行为：加入后命中，过期后自动清理"""
    from app.core.security import is_token_revoked, revoke_token

    jti = "test-jti-abcdef"
    exp = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 3600
    revoke_token(jti, exp)
    assert is_token_revoked(jti) is True
    # 过期条目：命中时被清理并返回 False
    past = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) - 1
    revoke_token("expired-jti", past)
    assert is_token_revoked("expired-jti") is False
    assert is_token_revoked("never-seen") is False


# ---------- /uploads 鉴权 ----------

@pytest.fixture()
def upload_file():
    """在上传目录造一个临时文件，测试后删除"""
    target = config.UPLOAD_DIR / "face" / "test_upload_auth.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"fake-image-bytes")
    yield target
    target.unlink(missing_ok=True)


def test_uploads_requires_login(upload_file):
    # 未登录：即使文件存在也 401
    resp = client.get("/uploads/face/test_upload_auth.jpg")
    assert resp.status_code == 200  # 业务码在 body（项目约定 HTTP 恒 200）
    assert resp.json()["code"] == 401


def test_uploads_serve_after_login(upload_file):
    cookies = TestClient(app).post(
        "/api/auth/login",
        json={"username": USERNAME, "password": "123456"},
    ).cookies.get("sc_token")
    resp = client.get(
        "/uploads/face/test_upload_auth.jpg",
        cookies={"sc_token": cookies},
    )
    assert resp.status_code == 200
    assert resp.content == b"fake-image-bytes"


def test_uploads_traversal_blocked():
    """路径穿越必须被拦截（直接调函数级，绕过 HTTP 客户端路径规范化）"""
    # 构造伪 CurrentUser（鉴权已由路由依赖完成，这里只测路径校验逻辑）
    from collections import namedtuple
    FakeUser = namedtuple("FakeUser", ["student_no", "name", "status"])
    fake_current = namedtuple("Current", ["user", "role", "jti", "exp"])(
        user=FakeUser(USERNAME, "张三", 1), role="student", jti="x", exp=0
    )
    for evil in ["../config.py", "..\\..\\.env", "face/../../main.py"]:
        with pytest.raises(BizError) as exc_info:
            serve_upload(evil, fake_current)
        assert exc_info.value.code == 404

    # 不存在的文件同样 404
    with pytest.raises(BizError) as exc_info:
        serve_upload("face/no_such_file.jpg", fake_current)
    assert exc_info.value.code == 404
