# -*- coding: utf-8 -*-
"""考勤相关 ORM 模型：签到会话 / 签到记录 / 学业预警（字段与线上库 DDL 一致）"""
from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import TINYINT

from app.database import Base


class CheckinSession(Base):
    """签到会话表（教师发起的一次签到，含经纬度与有效范围）"""

    __tablename__ = "checkin_session"
    __table_args__ = (
        Index("idx_course_id", "course_id"),
        Index("idx_teacher_id", "teacher_id"),
        {"comment": "签到会话表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="会话ID")
    course_id = Column(String(20), nullable=False, comment="课程ID")
    teacher_id = Column(String(20), nullable=False, comment="发起教师ID")
    teacher_lat = Column(Float, comment="教师纬度")
    teacher_lng = Column(Float, comment="教师经度")
    teacher_photo_url = Column(
        String(500), comment="教师现场照片URL(用于三重核验第二重)"
    )
    range_meters = Column(Integer, server_default=text("200"), comment="有效范围(米)")
    duration_minutes = Column(Integer, server_default=text("5"), comment="签到时长(分钟)")
    status = Column(Integer, server_default=text("1"), comment="状态: 1-进行中, 0-已结束")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), comment="创建")
    end_time = Column(DateTime, comment="结束")


class AttendanceRecord(Base):
    """签到记录表（外键 fk_att_session 由 scripts/init_db.py 增量补齐）"""

    __tablename__ = "attendance_record"
    __table_args__ = (
        Index("idx_course_date", "course_id", "attendance_date"),
        Index("idx_student_id", "student_id"),
        Index("idx_student_course_status", "student_id", "course_id", "status"),
        Index("idx_status", "status"),
        Index("idx_session_id", "session_id"),
        {"comment": "签到记录表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    course_id = Column(
        String(20),
        ForeignKey("course.course_code", ondelete="RESTRICT"),
        nullable=False,
        comment="课程ID",
    )
    student_id = Column(
        String(20),
        ForeignKey("student.student_no", ondelete="RESTRICT"),
        nullable=False,
        comment="学生ID",
    )
    schedule_id = Column(BigInteger, comment="课程安排ID")
    attendance_date = Column(Date, nullable=False, comment="考勤日期")
    status = Column(TINYINT, nullable=False, comment="状态: 0-缺勤, 1-正常, 2-迟到, 3-早退, 4-请假")
    check_in_time = Column(DateTime, comment="签到时间")
    check_in_type = Column(TINYINT, comment="签到方式: 1-人脸, 2-补签")
    location = Column(String(200), comment="签到位置")
    device_info = Column(String(500), comment="设备信息")
    student_image_url = Column(String(500), comment="学生自拍照片URL")
    similarity1 = Column(Numeric(5, 4), comment="学生自拍与模板相似度")
    is_liveness_passed = Column(TINYINT, comment="活体检测是否通过")
    review_status = Column(TINYINT, server_default=text("0"), comment="审核状态: 0-正常, 1-待审核, 2-已审核")
    review_remark = Column(String(500), comment="审核备注")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    session_id = Column(
        BigInteger,
        ForeignKey("checkin_session.id"),
        comment="签到会话ID",
    )


class AcademicAlert(Base):
    """学业预警表（由出勤率/成绩等触发，辅导员处理）"""

    __tablename__ = "academic_alert"
    __table_args__ = (
        Index("idx_student_id", "student_id"),
        Index("idx_course_id", "course_id"),
        Index("idx_status", "status"),
        Index("idx_severity", "severity"),
        Index("idx_handler_id", "handler_id"),
        {"comment": "学业预警表"},
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="预警ID")
    student_id = Column(
        String(20),
        ForeignKey("student.student_no", ondelete="RESTRICT"),
        nullable=False,
        comment="学生ID",
    )
    course_id = Column(
        String(20),
        ForeignKey("course.course_code", ondelete="RESTRICT"),
        comment="课程ID",
    )
    alert_type = Column(String(50), comment="预警类型")
    reason = Column(Text, comment="预警原因")
    status = Column(TINYINT, server_default=text("0"), comment="状态: 0-未处理, 1-已处理")
    is_resolved = Column(TINYINT, server_default=text("0"), comment="是否已解决")
    is_read = Column(TINYINT, server_default=text("0"), comment="是否已读")
    create_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    update_time = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    severity = Column(TINYINT, server_default=text("1"), comment="严重程度: 1-轻度, 2-中度, 3-重度")
    trigger_condition = Column(
        String(200), comment="触发条件，如: 出勤率<70%, 平均分<60, 缺勤>=5次"
    )
    handler_id = Column(BigInteger, comment="处理人ID（辅导员）")
    handle_time = Column(DateTime, comment="处理时间")
    handle_remark = Column(Text, comment="处理备注/帮扶措施")
