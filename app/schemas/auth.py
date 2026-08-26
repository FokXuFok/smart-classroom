# -*- coding: utf-8 -*-
"""认证相关请求/响应模型"""
from typing import Literal, Optional

from pydantic import BaseModel


class LoginReq(BaseModel):
    """登录：不指定角色，后端根据账号自动判断身份"""

    username: str
    password: str


class RegisterReq(BaseModel):
    """自助注册：仅学生 / 教师，注册后 status=0 待管理员审批"""

    username: str
    password: str
    name: str
    role: Literal["student", "teacher"]
    class_id: Optional[str] = None  # role=student 时必填
