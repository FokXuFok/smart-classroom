# -*- coding: utf-8 -*-
"""通用请求模型：分页 + 人员/课程/班级/选课/课表/课堂互动"""
import datetime
from typing import Optional

from pydantic import BaseModel


class PageReq(BaseModel):
    page: int = 1
    page_size: int = 20


# ---------- 人员 ----------

class UserCreateReq(BaseModel):
    role: str  # student / teacher / counselor
    user_no: str  # 学号 / 工号 / 编号
    name: str
    password: Optional[str] = None  # 默认 123456
    gender: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None  # 教师 / 辅导员
    title: Optional[str] = None  # 教师职称
    class_id: Optional[str] = None  # 学生所属班级


class UserUpdateReq(BaseModel):
    """全可选（不含密码；密码走 reset-password）"""

    name: Optional[str] = None
    gender: Optional[int] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    title: Optional[str] = None
    status: Optional[int] = None
    class_id: Optional[str] = None  # 学生


# ---------- 课程 / 班级 / 选课 / 课表 ----------

class CourseCreateReq(BaseModel):
    course_id: str  # 课程代码
    course_name: str
    credit: Optional[float] = None
    hours: Optional[int] = None
    description: Optional[str] = None
    semester: Optional[str] = None
    teacher_id: str
    status: Optional[int] = 1


class CourseUpdateReq(BaseModel):
    """全可选"""

    course_name: Optional[str] = None
    credit: Optional[float] = None
    hours: Optional[int] = None
    description: Optional[str] = None
    semester: Optional[str] = None
    teacher_id: Optional[str] = None
    status: Optional[int] = None


class ClassCreateReq(BaseModel):
    class_id: str  # 班级代码
    class_name: str
    grade: Optional[str] = None
    major: Optional[str] = None
    department: Optional[str] = None


class ClassUpdateReq(BaseModel):
    """全可选（student_count 动态统计，不接受手填）"""

    class_name: Optional[str] = None
    grade: Optional[str] = None
    major: Optional[str] = None
    department: Optional[str] = None


class EnrollmentCreateReq(BaseModel):
    course_id: str
    student_no: str


class ScheduleCreateReq(BaseModel):
    course_id: str
    class_id: str
    weekday: int  # 1-7
    start_time: datetime.time
    end_time: datetime.time
    weeks: Optional[str] = None
    classroom: Optional[str] = None


# ---------- 课堂互动 ----------

class InteractionCreateReq(BaseModel):
    course_id: str
    interaction_type: str  # question / rating / random_pick
    student_id: Optional[str] = None
    content: Optional[str] = None
    score: Optional[int] = None
    lesson_date: Optional[datetime.date] = None  # 默认今天
