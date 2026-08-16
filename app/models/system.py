# -*- coding: utf-8 -*-
"""系统相关 ORM 模型：审计日志 / 登录尝试（字段与线上库 DDL 一致）"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)

from app.database import Base


class AuditLog(Base):
    """审计日志表"""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_user_time", "user_id", "create_time"),
        Index("idx_action_time", "action", "create_time"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(50), nullable=False)
    user_role = Column(String(20), nullable=False)
    action = Column(String(50), nullable=False)
    target_type = Column(String(30))
    target_id = Column(String(50))
    detail = Column(Text)
    ip = Column(String(45))
    create_time = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class LoginAttempt(Base):
    """登录尝试表（失败计数与锁定）"""

    __tablename__ = "login_attempt"
    __table_args__ = (
        UniqueConstraint("username", name="username"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False)
    fail_count = Column(Integer, nullable=False, server_default=text("0"))
    lock_until = Column(DateTime)
    last_fail_time = Column(DateTime)
    update_time = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
