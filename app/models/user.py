# -*- coding: utf-8 -*-
"""用户相关 ORM 模型：学生 / 教师 / 辅导员 / 管理员（字段与线上库 DDL 一致）"""
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT

from app.database import Base


class Student(Base):
    """学生信息表"""

    __tablename__ = "student"
    __table_args__ = (
        Index("idx_student_no", "student_no"),
        {"comment": "学生信息表"},
    )

    student_no = Column(String(20), primary_key=True, comment="学号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(TINYINT, comment="性别: 0-女, 1-男")
    phone = Column(String(20), comment="手机号")
    email = Column(String(100), comment="邮箱")
    face_template = Column(
        LargeBinary, comment="人脸特征向量（InsightFace 512维 float32）"
    )
    face_image_url = Column(String(500), comment="人脸照片URL")
    password = Column(
        String(100), server_default=text("'123456'"), comment="登录密码"
    )
    status = Column(TINYINT, server_default=text("1"), comment="状态: 0-禁用, 1-正常")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    face_regen_allowed = Column(
        TINYINT, server_default=text("0"), comment="教师授权重注册: 0-不允许, 1-允许"
    )
    class_id = Column(String(20), nullable=False)


class Teacher(Base):
    """教师信息表"""

    __tablename__ = "teacher"
    __table_args__ = (
        Index("idx_teacher_no", "teacher_no"),
        {"comment": "教师信息表"},
    )

    teacher_no = Column(String(20), primary_key=True, comment="教师工号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(TINYINT, comment="性别: 0-女, 1-男")
    phone = Column(String(20), comment="手机号")
    email = Column(String(100), comment="邮箱")
    department = Column(String(100), comment="所属院系")
    title = Column(String(50), comment="职称")
    face_template = Column(LargeBinary, comment="人脸特征模板(AES加密)")
    password = Column(
        String(100), server_default=text("'123456'"), comment="登录密码"
    )
    status = Column(TINYINT, server_default=text("1"), comment="状态: 0-禁用, 1-正常")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class Counselor(Base):
    """辅导员信息表"""

    __tablename__ = "counselor"
    __table_args__ = (
        UniqueConstraint("counselor_no", name="counselor_no"),
        Index("idx_counselor_no", "counselor_no"),
        {"comment": "辅导员信息表"},
    )

    counselor_no = Column(String(20), primary_key=True, comment="辅导员编号")
    name = Column(String(50), nullable=False, comment="姓名")
    gender = Column(TINYINT, comment="性别: 0-女, 1-男")
    phone = Column(String(20), comment="手机号")
    email = Column(String(100), comment="邮箱")
    department = Column(String(100), comment="所属院系")
    password = Column(
        String(100), server_default=text("'123456'"), comment="登录密码"
    )
    status = Column(TINYINT, server_default=text("1"), comment="状态: 0-禁用, 1-正常")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class Admin(Base):
    """管理员信息表（增量升级新建，密码存 bcrypt 哈希）"""

    __tablename__ = "admin"
    __table_args__ = {
        "comment": "管理员信息表",
        "mysql_charset": "utf8mb4",
        "mysql_collate": "utf8mb4_0900_ai_ci",
    }

    admin_no = Column(String(20), primary_key=True, comment="管理员编号")
    name = Column(String(50), nullable=False, comment="姓名")
    password = Column(String(100), nullable=False, comment="登录密码（bcrypt 哈希）")
    status = Column(TINYINT, server_default=text("1"), comment="状态: 0-禁用, 1-正常")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
