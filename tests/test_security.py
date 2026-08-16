# -*- coding: utf-8 -*-
"""安全层 + 登录认证测试（打真实库）"""
import datetime

import jwt
import pytest
from fastapi.testclient import TestClient

import config
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
    resp = client.post(
        "/api/auth/login",
        json={"username": USERNAME, "password": "123456", "role": "student"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    token = body["data"]["token"]
    assert body["data"]["role"] == "student"
    assert body["data"]["user_id"] == USERNAME

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    me_body = me.json()
    assert me_body["code"] == 0
    assert me_body["data"]["name"] == "张三"
    assert me_body["data"]["class_id"] == "CLS001"


def test_me_without_token():
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
