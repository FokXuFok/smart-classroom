# -*- coding: utf-8 -*-
"""课堂互动与 AI 相关 ORM 模型：互动 / AI问答 / 知识库 / 评分规则 / 常见错误 / 通知（字段与线上库 DDL 一致）"""
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT

from app.database import Base


class ClassroomInteraction(Base):
    """课堂互动记录表（提问/评分等）"""

    __tablename__ = "classroom_interaction"
    __table_args__ = (
        Index("idx_course_id", "course_id"),
        Index("idx_student_id", "student_id"),
        Index("idx_lesson_date", "lesson_date"),
        {"comment": "课堂互动记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="互动ID")
    course_id = Column(
        String(20),
        ForeignKey("course.course_code", ondelete="CASCADE"),
        nullable=False,
        comment="课程ID",
    )
    student_id = Column(String(20), comment="学生ID")
    interaction_type = Column(String(50), comment="互动类型: question/rating")
    content = Column(Text, comment="互动内容")
    score = Column(Integer, comment="评分")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    teacher_id = Column(String(20), comment="教师工号")
    lesson_date = Column(Date, comment="上课日期")


class AiQaRecord(Base):
    """AI 问答记录表"""

    __tablename__ = "ai_qa_record"
    __table_args__ = (
        Index("idx_course_id", "course_id"),
        Index("idx_student_id", "student_id"),
        {"comment": "AI问答记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    course_id = Column(String(20), comment="课程ID")
    student_id = Column(String(20), comment="学生ID")
    question = Column(Text, comment="问题")
    answer = Column(Text, comment="回答")
    is_anonymous = Column(TINYINT, server_default=text("0"), comment="是否匿名")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class AiKnowledgeBase(Base):
    """AI 知识库表"""

    __tablename__ = "ai_knowledge_base"
    __table_args__ = (
        Index("idx_course_id", "course_id"),
        Index("idx_subject", "subject"),
        {"comment": "AI知识库表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="知识点ID")
    course_id = Column(String(20), comment="课程ID（为空表示通用知识点）")
    subject = Column(String(100), comment="学科/主题")
    title = Column(String(200), nullable=False, comment="知识点标题")
    content = Column(Text, comment="知识点内容")
    difficulty = Column(Integer, server_default=text("1"), comment="难度: 1-入门 2-基础 3-进阶 4-高级")
    sort_order = Column(Integer, server_default=text("0"), comment="排序")
    status = Column(Integer, server_default=text("1"), comment="状态: 0-禁用, 1-启用")
    create_time = Column(DateTime, comment="创建")
    update_time = Column(DateTime, comment="更新")


class AiScoringRule(Base):
    """AI 评分规则表"""

    __tablename__ = "ai_scoring_rule"
    __table_args__ = (
        Index("idx_course_id", "course_id"),
        Index("idx_subject", "subject"),
        {"comment": "AI评分规则表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="规则ID")
    course_id = Column(String(20), comment="课程ID（为空表示通用规则）")
    subject = Column(String(100), comment="学科/主题")
    name = Column(String(100), nullable=False, comment="规则名称")
    content = Column(Text, nullable=False, comment="规则内容")
    weight = Column(Float, server_default=text("0"), comment="权重百分比 0-100")
    sort_order = Column(Integer, server_default=text("0"), comment="排序")
    status = Column(Integer, server_default=text("1"), comment="状态: 0-禁用, 1-启用")
    create_time = Column(DateTime, comment="创建")
    update_time = Column(DateTime, comment="更新")
    rule_type = Column(
        String(20), server_default=text("'score_point'"), comment="规则类型: score_point/deduct"
    )
    max_score = Column(Float, server_default=text("0"), comment="该规则满分")
    criteria = Column(Text, comment="判定条件描述")


class AiCommonError(Base):
    """AI 常见错误表"""

    __tablename__ = "ai_common_error"
    __table_args__ = (
        Index("idx_course_id", "course_id"),
        Index("idx_subject", "subject"),
        Index("idx_error_type", "error_type"),
        {"comment": "AI常见错误表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="错误ID")
    course_id = Column(String(20), comment="课程ID（为空表示通用错误）")
    subject = Column(String(100), comment="学科/主题")
    error_type = Column(String(50), comment="错误类型: syntax/logic/runtime/performance")
    content = Column(Text, nullable=False, comment="错误描述")
    solution = Column(Text, comment="解决方案")
    example = Column(Text, comment="错误示例代码")
    sort_order = Column(Integer, server_default=text("0"), comment="排序")
    status = Column(Integer, server_default=text("1"), comment="状态: 0-禁用, 1-启用")
    create_time = Column(DateTime, comment="创建")
    update_time = Column(DateTime, comment="更新")


class Notification(Base):
    """通知表"""

    __tablename__ = "notification"
    __table_args__ = (
        Index("idx_user_id", "user_id"),
        Index("idx_course_id", "course_id"),
        Index("idx_user_type_is_read", "user_id", "user_type", "is_read"),
        {"comment": "通知表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="通知ID")
    user_id = Column(BigInteger, nullable=False, comment="接收用户ID")
    user_type = Column(
        String(20), server_default=text("'student'"), comment="用户类型: student/teacher"
    )
    notif_type = Column(String(50), comment="通知类型: homework_publish/homework_graded/attendance etc.")
    title = Column(String(200), comment="通知标题")
    content = Column(Text, comment="通知内容")
    related_id = Column(BigInteger, comment="关联对象ID（如作业ID）")
    course_id = Column(String(20), comment="课程ID")
    is_read = Column(Integer, server_default=text("0"), comment="是否已读: 0-未读, 1-已读")
    create_time = Column(DateTime, comment="创建")
