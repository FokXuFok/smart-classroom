# -*- coding: utf-8 -*-
"""课程组织相关 ORM 模型：课程 / 班级 / 选课 / 课表 / 辅导员-班级（字段与线上库 DDL 一致）"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    PrimaryKeyConstraint,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT

from app.database import Base


class Course(Base):
    """课程信息表"""

    __tablename__ = "course"
    __table_args__ = (
        Index("idx_course_code", "course_code"),
        Index("idx_teacher_id", "teacher_id"),
        {"comment": "课程信息表"},
    )

    course_code = Column(String(20), primary_key=True, comment="课程代码")
    course_name = Column(String(100), nullable=False, comment="课程名称")
    credit = Column(Numeric(3, 1), comment="学分")
    hours = Column(Integer, comment="学时")
    description = Column(Text, comment="课程描述")
    semester = Column(String(20), comment="学期")
    teacher_id = Column(
        String(20),
        ForeignKey("teacher.teacher_no", ondelete="CASCADE"),
        nullable=False,
        comment="授课教师ID",
    )
    status = Column(TINYINT, server_default=text("1"), comment="状态: 0-停用, 1-正常")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class ClassInfo(Base):
    """班级信息表（表名 class 为 Python 保留字，故类名用 ClassInfo）"""

    __tablename__ = "class"
    __table_args__ = (
        Index("idx_class_name", "class_name"),
        Index("idx_class_code", "class_code"),
        {"comment": "班级信息表"},
    )

    class_code = Column(String(20), primary_key=True)
    class_name = Column(String(100), nullable=False, comment="班级名称")
    grade = Column(String(10), comment="年级")
    major = Column(String(100), comment="专业")
    department = Column(String(100), comment="所属院系")
    student_count = Column(Integer, server_default=text("0"), comment="学生人数")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class Enrollment(Base):
    """选课关系表"""

    __tablename__ = "enrollment"
    __table_args__ = (
        UniqueConstraint("course_id", "student_id", name="uk_course_student"),
        Index("idx_course_id", "course_id"),
        Index("idx_student_id", "student_id"),
        {"comment": "选课关系表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="选课ID")
    course_id = Column(
        String(20),
        ForeignKey("course.course_code", ondelete="CASCADE"),
        nullable=False,
        comment="课程ID",
    )
    student_id = Column(
        String(20),
        ForeignKey("student.student_no", ondelete="CASCADE"),
        nullable=False,
        comment="学生ID",
    )
    status = Column(TINYINT, server_default=text("1"), comment="状态: 0-退选, 1-正常")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class Schedule(Base):
    """课表（增量升级新建：某班某课每周固定时段的上课安排）"""

    __tablename__ = "schedule"
    __table_args__ = (
        UniqueConstraint(
            "course_id", "class_id", "weekday", "start_time", name="uk_schedule_slot"
        ),
        {
            "comment": "课表",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
        },
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    course_id = Column(
        String(20),
        ForeignKey("course.course_code", ondelete="CASCADE"),
        nullable=False,
        comment="课程代码",
    )
    class_id = Column(
        String(20),
        ForeignKey("class.class_code", ondelete="CASCADE"),
        nullable=False,
        comment="班级代码",
    )
    weekday = Column(TINYINT, nullable=False, comment="星期几: 1-7")
    start_time = Column(Time, nullable=False, comment="上课时间")
    end_time = Column(Time, nullable=False, comment="下课时间")
    weeks = Column(String(50), server_default=text("'1-16'"), comment="周次")
    classroom = Column(String(100), comment="教室")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class CounselorClass(Base):
    """辅导员-班级关联表"""

    __tablename__ = "counselor_class"
    __table_args__ = (
        PrimaryKeyConstraint("counselor_id", "class_id"),
        Index("idx_counselor_id", "counselor_id"),
        Index("idx_class_id", "class_id"),
        {"comment": "辅导员-班级关联表"},
    )

    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    class_id = Column(String(20), nullable=False)
    counselor_id = Column(String(20), nullable=False)
