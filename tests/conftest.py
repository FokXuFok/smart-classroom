# -*- coding: utf-8 -*-
"""pytest 全局工具

认证说明：登录 token 经按角色命名的 httpOnly cookie（sc_token_student /
sc_token_teacher / ...）下发，登录响应体不再含 token 字段。同一浏览器可
同时登录多个角色（多角色 cookie 并存），各角色页面互不影响。登录一律走
一次性 TestClient（login_cookies），发请求时显式传 cookies=…；越权场景用
forge_cookies 伪造带当前 instance_id 的身份。
"""
import config
from fastapi.testclient import TestClient

from app.core.security import create_token
from app.main import app


def login_cookies(username: str, password: str, role: str = None) -> dict:
    """真实登录并返回对应角色 cookie dict：{sc_token_{role}: <jwt>}

    role 参数仅作调用方声明（供断言），实际以登录响应判断的角色为准。
    """
    resp = TestClient(app).post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    body = resp.json()
    assert body["code"] == 0, f"登录失败: {body}"
    actual_role = body["data"]["role"]
    token = resp.cookies.get(f"sc_token_{actual_role}")
    assert token, f"登录响应未下发 sc_token_{actual_role} cookie"
    return {f"sc_token_{actual_role}": token}


def forge_cookies(user_id: str, role: str, name: str = "测试") -> dict:
    """伪造指定身份的 cookie（签发时带当前 instance_id，可通过会话校验）"""
    return {
        f"sc_token_{role}": create_token(user_id, role, name, config.INSTANCE_ID)
    }
