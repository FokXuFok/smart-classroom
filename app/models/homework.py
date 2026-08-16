# -*- coding: utf-8 -*-
"""作业相关 ORM 模型：作业 / 测试用例 / 提交记录 / 成绩册 / 代码查重 / 错误归类（字段与线上库 DDL 一致）"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import DOUBLE, LONGTEXT, TINYINT

from app.database import Base


class Homework(Base):
    """作业信息表"""

    __tablename__ = "homework"
    __table_args__ = (
        Index("idx_course_id", "course_id"),
        Index("idx_deadline", "deadline"),
        Index("idx_teacher_id", "teacher_id"),
        {"comment": "作业信息表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="作业ID")
    course_id = Column(
        String(20),
        ForeignKey("course.course_code", ondelete="CASCADE"),
        nullable=False,
        comment="课程ID",
    )
    teacher_id = Column(String(20), comment="发布教师ID")
    title = Column(String(200), nullable=False, comment="作业标题")
    description = Column(Text, comment="作业描述")
    programming_language = Column(String(20), comment="编程语言")
    max_score = Column(DOUBLE, server_default=text("100"), comment="总分")
    deadline = Column(DateTime, comment="截止时间")
    allow_late_submit = Column(TINYINT, server_default=text("0"), comment="是否允许迟交")
    status = Column(TINYINT, server_default=text("1"), comment="状态: 0-草稿, 1-已发布, 2-已截止")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    feedback_visible = Column(
        Integer, server_default=text("0"), comment="AI反馈开放: 0=按截止时间自动, 1=教师已提前开放"
    )


class TestCase(Base):
    """测试用例表"""

    __tablename__ = "test_case"
    __table_args__ = (
        Index("idx_homework_id", "homework_id"),
        {"comment": "测试用例表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用例ID")
    homework_id = Column(
        BigInteger,
        ForeignKey("homework.id", ondelete="CASCADE"),
        nullable=False,
        comment="作业ID",
    )
    name = Column(String(100), comment="用例名称")
    test_input = Column(Text, comment="输入数据")
    expected_output = Column(Text, comment="期望输出")
    score_weight = Column(DOUBLE, comment="分值权重")
    is_public = Column(TINYINT, server_default=text("0"), comment="是否公开")
    time_limit = Column(Integer, server_default=text("1000"), comment="时间限制(ms)")
    memory_limit = Column(Integer, server_default=text("256"), comment="内存限制(MB)")
    order_num = Column(Integer, server_default=text("0"), comment="排序")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class SubmissionRecord(Base):
    """作业提交记录表"""

    __tablename__ = "submission_record"
    __table_args__ = (
        Index("idx_homework_id", "homework_id"),
        Index("idx_student_id", "student_id"),
        Index("idx_status", "status"),
        Index("idx_course_id", "course_id"),
        Index("idx_submit_time", "submit_time"),
        {"comment": "作业提交记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="提交ID")
    homework_id = Column(
        BigInteger,
        ForeignKey("homework.id", ondelete="RESTRICT"),
        nullable=False,
        comment="作业ID",
    )
    student_id = Column(
        String(20),
        ForeignKey("student.student_no", ondelete="RESTRICT"),
        nullable=False,
        comment="学生ID",
    )
    course_id = Column(String(20), comment="课程ID")
    submitted_code = Column(LONGTEXT, comment="提交的代码")
    submit_time = Column(DateTime, comment="提交时间")
    status = Column(TINYINT, server_default=text("0"), comment="状态: 0-待评测, 1-已完成, 2-已批改")
    score = Column(DOUBLE, comment="得分")
    compile_error = Column(Text, comment="编译错误")
    test_results = Column(LONGTEXT, comment="测试结果JSON")
    ai_feedback = Column(Text, comment="AI反馈")
    judge_time = Column(DateTime, comment="评测时间")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class GradeBook(Base):
    """成绩册（每个学生每次作业取最高分）"""

    __tablename__ = "grade_book"
    __table_args__ = (
        UniqueConstraint("homework_id", "student_id", name="uk_gradebook_hw_stu"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    course_id = Column(String(20), nullable=False, comment="课程代码")
    homework_id = Column(BigInteger, nullable=False, comment="作业ID")
    student_id = Column(String(20), nullable=False, comment="学号")
    score = Column(Float, comment="得分（取最高分）")
    submit_count = Column(Integer, comment="提交次数")
    judge_time = Column(DateTime, comment="最后评测时间")
    create_time = Column(DateTime)
    update_time = Column(DateTime)


class CodeSimilarity(Base):
    """代码查重结果表（两两比对）"""

    __tablename__ = "code_similarity"
    __table_args__ = (
        UniqueConstraint(
            "homework_id", "student_a_id", "student_b_id",
            name="uk_homework_student_pair",
        ),
        Index("idx_homework_sim", "homework_id", "similarity"),
        Index("idx_student", "student_a_id", "student_b_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    homework_id = Column(BigInteger, nullable=False, comment="作业ID")
    student_a_id = Column(String(20), nullable=False, comment="学生A学号（字典序较小）")
    student_b_id = Column(String(20), nullable=False, comment="学生B学号（字典序较大）")
    similarity = Column(Float, nullable=False, comment="相似度 0-1")
    matched_fingerprint_count = Column(Integer, comment="匹配指纹数")
    submission_a_id = Column(BigInteger, comment="提交A的ID")
    submission_b_id = Column(BigInteger, comment="提交B的ID")
    check_time = Column(DateTime, comment="查重时间")


class ErrorClassification(Base):
    """提交错误归类表（规则或 AI 匹配常见错误）"""

    __tablename__ = "error_classification"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="归类ID")
    submission_id = Column(BigInteger, nullable=False, comment="提交记录ID")
    homework_id = Column(BigInteger, comment="作业ID")
    student_id = Column(String(20), comment="学号")
    error_id = Column(BigInteger, comment="匹配的常见错误ID（可为空）")
    error_type = Column(String(50), comment="错误类型: syntax/logic/runtime/boundary/performance")
    error_snippet = Column(Text, comment="错误片段（前200字）")
    matched_by = Column(String(20), comment="匹配方式: rule/ai")
    create_time = Column(DateTime)
