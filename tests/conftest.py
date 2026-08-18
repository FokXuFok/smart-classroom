# -*- coding: utf-8 -*-
"""pytest 全局工具

认证说明：登录 token 经 httpOnly cookie（sc_token_<role>）下发，登录响应体
不再含 token 字段。各测试模块共享的 TestClient 其 cookie jar 必须保持干净
（登录残留的其他角色 cookie 会被 deps._extract_token 按角色顺序抢先命中，
导致串号），因此登录一律走一次性 TestClient（login_cookies），发请求时
显式传 cookies=…；越权场景用 forge_cookies 伪造带当前 instance_id 的身份。
"""
import config
from fastapi.testclient import TestClient

from app.core.security import create_token
from app.main import app


def login_cookies(username: str, password: str, role: str) -> dict:
    """真实登录并返回该角色 cookie dict：{sc_token_<role>: <jwt>}"""
    resp = TestClient(app).post(
        "/api/auth/login",
        json={"username": username, "password": password, "role": role},
    )
    body = resp.json()
    assert body["code"] == 0, f"登录失败: {body}"
    token = resp.cookies.get(f"sc_token_{role}")
    assert token, f"登录响应未下发 sc_token_{role} cookie"
    return {f"sc_token_{role}": token}


def forge_cookies(user_id: str, role: str, name: str = "测试") -> dict:
    """伪造指定身份的 cookie（签发时带当前 instance_id，可通过会话校验）"""
    return {
        f"sc_token_{role}": create_token(user_id, role, name, config.INSTANCE_ID)
    }
