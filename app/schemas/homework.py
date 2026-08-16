# -*- coding: utf-8 -*-
"""作业模块请求模型"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TestCaseIn(BaseModel):
    name: str = ""
    test_input: str = ""
    expected_output: str = ""
    score_weight: float = 1.0
    is_public: bool = False


class HomeworkCreateReq(BaseModel):
    course_id: str
    title: str
    description: str = ""
    programming_language: str = "python"  # python/c/cpp/java
    max_score: float = 100
    deadline: Optional[datetime] = None
    allow_late_submit: bool = False
    test_cases: list[TestCaseIn] = []


class HomeworkUpdateReq(BaseModel):
    """全可选"""

    title: Optional[str] = None
    description: Optional[str] = None
    programming_language: Optional[str] = None
    max_score: Optional[float] = None
    deadline: Optional[datetime] = None
    allow_late_submit: Optional[bool] = None
    status: Optional[int] = None
    test_cases: Optional[list[TestCaseIn]] = None


class SubmitCodeReq(BaseModel):
    code: str
    language: str = "python"
