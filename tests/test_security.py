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
from app.models import LoginAttempt

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
        json={"username": USERNAME, "password": "123456", "role": "student"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    # token 现经 httpOnly cookie 下发，响应体不再含 token 字段
    cookie = resp.cookies.get("sc_token_student")
    assert cookie, "登录响应未下发 sc_token_student cookie"
    assert body["data"]["role"] == "student"
    assert body["data"]["user_id"] == USERNAME

    me = client.get("/api/auth/me", cookies={"sc_token_student": cookie})
    me_body = me.json()
    assert me_body["code"] == 0
    assert me_body["data"]["name"] == "张三"
    assert me_body["data"]["role"] == "student"
    assert me_body["data"]["user_id"] == USERNAME


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
            json={"username": USERNAME, "password": "wrong-pass", "role": "student"},
        )
        assert resp.json()["code"] == 1001

    # 第 6 次（即使密码正确）也被锁定拦截：1002
    resp = client.post(
        "/api/auth/login",
        json={"username": USERNAME, "password": "123456", "role": "student"},
    )
    assert resp.json()["code"] == 1002


# ---------- 登出黑名单：旧 token 立即失效 ----------

def test_logout_revokes_token():
    c = TestClient(app)
    c.post(
        "/api/auth/login",
        json={"username": USERNAME, "password": "123456", "role": "student"},
    )
    # 登出前可用
    assert c.get("/api/auth/me").json()["code"] == 0
    # 登出
    assert c.post("/api/auth/logout").json()["code"] == 0
    # 旧 token（即使 cookie 被恢复）已入黑名单 → 401
    resp = client.get(
        "/api/auth/me", cookies={"sc_token_student": c.cookies.get("sc_token_student")}
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
        json={"username": USERNAME, "password": "123456", "role": "student"},
    ).cookies.get("sc_token_student")
    resp = client.get(
        "/uploads/face/test_upload_auth.jpg",
        cookies={"sc_token_student": cookies},
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
