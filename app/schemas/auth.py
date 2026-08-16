# -*- coding: utf-8 -*-
"""认证相关请求/响应模型"""
from typing import Literal

from pydantic import BaseModel


class LoginReq(BaseModel):
    username: str
    password: str
    role: Literal["student", "teacher", "counselor", "admin"]
