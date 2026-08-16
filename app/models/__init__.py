# -*- coding: utf-8 -*-
"""ORM 模型层：从各子模块汇集全部模型类并统一导出"""
from app.models.user import Admin, Counselor, Student, Teacher
from app.models.course import (
    ClassInfo,
    CounselorClass,
    Course,
    Enrollment,
    Schedule,
)
from app.models.attendance import AcademicAlert, AttendanceRecord, CheckinSession
from app.models.homework import (
    CodeSimilarity,
    ErrorClassification,
    GradeBook,
    Homework,
    SubmissionRecord,
    TestCase,
)
from app.models.interaction import (
    AiCommonError,
    AiKnowledgeBase,
    AiQaRecord,
    AiScoringRule,
    ClassroomInteraction,
    Notification,
)
from app.models.system import AuditLog, LoginAttempt

__all__ = [
    # 用户
    "Student",
    "Teacher",
    "Counselor",
    "Admin",
    # 课程组织
    "Course",
    "ClassInfo",
    "Enrollment",
    "Schedule",
    "CounselorClass",
    # 考勤
    "CheckinSession",
    "AttendanceRecord",
    "AcademicAlert",
    # 作业
    "Homework",
    "TestCase",
    "SubmissionRecord",
    "GradeBook",
    "CodeSimilarity",
    "ErrorClassification",
    # 互动 / AI / 通知
    "ClassroomInteraction",
    "AiQaRecord",
    "AiKnowledgeBase",
    "AiScoringRule",
    "AiCommonError",
    "Notification",
    # 系统
    "AuditLog",
    "LoginAttempt",
]
