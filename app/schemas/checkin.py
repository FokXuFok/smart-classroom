# -*- coding: utf-8 -*-
"""签到模块请求模型"""
from typing import Literal, Optional

from pydantic import BaseModel


class StartCheckinReq(BaseModel):
    course_id: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    range_meters: int = 200
    duration_minutes: int = 5


class SubmitCheckinReq(BaseModel):
    session_id: int
    image_b64: str                       # 学生自拍（须包含教师屏幕上的签到二维码）
    lat: Optional[float] = None
    lng: Optional[float] = None
    fingerprint: Optional[str] = None    # 指纹数据（微信 SOTER）


class ApplyCheckinReq(BaseModel):
    session_id: int
    reason: str


class ReviewReq(BaseModel):
    action: Literal["approve", "reject"]
    remark: str = ""


class FaceRegisterReq(BaseModel):
    image_b64: str
