# -*- coding: utf-8 -*-
"""教师端 API：发起/结束签到、签到看板、补签审核、人脸重注册授权、我的课程"""
import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.api.deps import CurrentUser, get_db, require_roles
from app.api.notification import push
from app.core.exception import BizError, ok
from app.core.geofence import DEFAULT_COORD, haversine_m
from app.models import (
    AttendanceRecord,
    CheckinSession,
    Course,
    Enrollment,
    Student,
)
from app.schemas.checkin import ReviewReq, StartCheckinReq

router = APIRouter(prefix="/api/teacher", tags=["teacher-checkin"])

ATT_STATUS_CN = {0: "缺勤", 1: "正常", 2: "迟到", 3: "早退", 4: "请假"}


def session_dict(s: CheckinSession) -> dict:
    return {
        "id": s.id,
        "course_id": s.course_id,
        "teacher_id": s.teacher_id,
        "teacher_lat": s.teacher_lat,
        "teacher_lng": s.teacher_lng,
        "range_meters": s.range_meters,
        "duration_minutes": s.duration_minutes,
        "status": s.status,
        "create_time": s.create_time,
        "end_time": s.end_time,
    }


# ---------- 发起签到 ----------

@router.post("/checkin/start")
def start_checkin(
    req: StartCheckinReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    course = (
        db.query(Course).filter(Course.course_code == req.course_id).first()
    )
    if course is None:
        raise BizError(404, "课程不存在")
    if course.teacher_id != current.user.teacher_no:
        raise BizError(403, "无权限操作该课程")

    used_default = req.lat is None or req.lng is None
    lat, lng = (req.lat, req.lng) if not used_default else DEFAULT_COORD

    now = datetime.datetime.now()
    session = CheckinSession(
        course_id=req.course_id,
        teacher_id=current.user.teacher_no,
        teacher_lat=lat,
        teacher_lng=lng,
        range_meters=req.range_meters,
        duration_minutes=req.duration_minutes,
        status=1,
        create_time=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    deadline = session.create_time + datetime.timedelta(
        minutes=session.duration_minutes or 5
    )
    return ok(
        {
            **session_dict(session),
            "deadline": deadline,
            "used_default": used_default,
        },
        message="签到已发起",
    )


# ---------- 结束签到（未签学生补缺勤） ----------

@router.post("/checkin/{session_id}/end")
def end_checkin(
    session_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    session = db.query(CheckinSession).filter(CheckinSession.id == session_id).first()
    if session is None:
        raise BizError(404, "签到会话不存在")
    if session.teacher_id != current.user.teacher_no:
        raise BizError(403, "无权限操作该会话")

    now = datetime.datetime.now()
    if session.status == 1:
        session.status = 0
        session.end_time = now
        db.commit()

    # 选课名单中无本次会话记录的学生 → 补写缺勤
    enrolled = (
        db.query(Student.student_no)
        .join(
            Enrollment,
            (Enrollment.student_id == Student.student_no)
            & (Enrollment.course_id == session.course_id)
            & (Enrollment.status == 1),
        )
        .all()
    )
    signed = {
        sno
        for (sno,) in db.query(AttendanceRecord.student_id).filter(
            AttendanceRecord.session_id == session_id
        )
    }
    today = datetime.date.today()
    absent_created = 0
    for (sno,) in enrolled:
        if sno not in signed:
            db.add(
                AttendanceRecord(
                    course_id=session.course_id,
                    student_id=sno,
                    attendance_date=today,
                    status=0,
                    session_id=session_id,
                )
            )
            absent_created += 1
    db.commit()

    stats = dict(
        db.query(AttendanceRecord.status, func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.session_id == session_id)
        .group_by(AttendanceRecord.status)
        .all()
    )
    return ok(
        {
            "session_id": session_id,
            "status": session.status,
            "student_total": len(enrolled),
            "absent_created": absent_created,
            "stats": {ATT_STATUS_CN[k]: v for k, v in stats.items()},
        },
        message="签到已结束",
    )


# ---------- 会话历史（本人最近 50 条） ----------

@router.get("/checkin/sessions")
def list_checkin_sessions(
    course_id: str = None,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    """本人签到会话历史（倒序 50 条，course_id 可选过滤）"""
    signed_sub = (
        db.query(func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.session_id == CheckinSession.id)
        .correlate(CheckinSession)
        .scalar_subquery()
    )
    q = (
        db.query(CheckinSession, Course.course_name, signed_sub)
        .outerjoin(Course, Course.course_code == CheckinSession.course_id)
        .filter(CheckinSession.teacher_id == current.user.teacher_no)
    )
    if course_id:
        q = q.filter(CheckinSession.course_id == course_id)
    rows = q.order_by(CheckinSession.id.desc()).limit(50).all()

    data = [
        {
            **session_dict(s),
            "course_name": course_name,
            "signed_count": signed or 0,
        }
        for s, course_name, signed in rows
    ]
    return ok(data)


# ---------- 签到看板 ----------

@router.get("/checkin/dashboard/{session_id}")
def dashboard(
    session_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    session = db.query(CheckinSession).filter(CheckinSession.id == session_id).first()
    if session is None:
        raise BizError(404, "签到会话不存在")
    if session.teacher_id != current.user.teacher_no:
        raise BizError(403, "无权限查看该会话")

    rows = (
        db.query(Student, AttendanceRecord)
        .join(
            Enrollment,
            (Enrollment.student_id == Student.student_no)
            & (Enrollment.course_id == session.course_id)
            & (Enrollment.status == 1),
        )
        .outerjoin(
            AttendanceRecord,
            (AttendanceRecord.session_id == session.id)
            & (AttendanceRecord.student_id == Student.student_no),
        )
        .order_by(Student.student_no)
        .all()
    )

    students = []
    for st, rec in rows:
        distance_hint = None
        if rec is not None and rec.location:
            try:
                slat, slng = (float(x) for x in rec.location.split(","))
                distance_hint = round(
                    haversine_m(session.teacher_lat, session.teacher_lng, slat, slng)
                )
            except (ValueError, TypeError):
                distance_hint = None
        students.append(
            {
                # 前端审核入口需要 record_id 定位考勤记录
                "record_id": rec.id if rec else None,
                "review_remark": rec.review_remark if rec else None,
                "student_no": st.student_no,
                "name": st.name,
                "status": (
                    ("未签到" if session.status == 1 else "缺勤")
                    if rec is None
                    else ATT_STATUS_CN.get(rec.status, str(rec.status))
                ),
                "check_in_time": rec.check_in_time if rec else None,
                "similarity1": float(rec.similarity1) if rec and rec.similarity1 is not None else None,
                "location": rec.location if rec else None,
                "distance_hint": distance_hint,
                "review_status": rec.review_status if rec else None,
            }
        )

    return ok({"session": session_dict(session), "students": students})


# ---------- 补签/请假审核 ----------

@router.post("/checkin/attendance/{record_id}/review")
def review_attendance(
    record_id: int,
    req: ReviewReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    rec = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    if rec is None:
        raise BizError(404, "签到记录不存在")
    # 归属校验：只能审核本人授课课程的考勤记录
    course = db.query(Course).filter(Course.course_code == rec.course_id).first()
    if course is None or course.teacher_id != current.user.teacher_no:
        raise BizError(403, "无权限审核该记录")

    if req.action == "approve":
        if rec.status == 0:  # 缺勤 → 补签为正常
            rec.status = 1
            rec.check_in_type = 2
        rec.review_status = 2
    else:  # reject
        rec.review_status = 2
    rec.review_remark = req.remark
    db.commit()
    db.refresh(rec)
    # 通知钩子：签到审核结果通知学生（push 内部自带异常兜底）
    push(
        db,
        rec.student_id,
        "student",
        "attendance_review",
        "签到审核结果",
        f"您的签到申请已{'通过' if req.action == 'approve' else '驳回'}"
        f"（当前状态：{ATT_STATUS_CN.get(rec.status, str(rec.status))}）。",
        related_id=rec.id,
        course_id=rec.course_id,
    )
    return ok(
        {
            "id": rec.id,
            "status": ATT_STATUS_CN.get(rec.status, rec.status),
            "check_in_type": rec.check_in_type,
            "review_status": rec.review_status,
            "review_remark": rec.review_remark,
        },
        message="审核完成",
    )


# ---------- 授权学生重新注册人脸 ----------

@router.put("/student/{student_no}/face-regen")
def allow_face_regen(
    student_no: str,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    st = db.query(Student).filter(Student.student_no == student_no).first()
    if st is None:
        raise BizError(404, "学生不存在")
    st.face_regen_allowed = 1
    db.commit()
    return ok(
        {"student_no": student_no, "face_regen_allowed": 1},
        message="已授权该学生重新注册人脸",
    )


# ---------- 我的课程 ----------

@router.get("/courses")
def my_courses(
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    courses = (
        db.query(Course)
        .filter(Course.teacher_id == current.user.teacher_no, Course.status == 1)
        .order_by(Course.course_code)
        .all()
    )
    # 批量聚合各课程在册学生数，避免逐课 N+1 查询
    code_list = [c.course_code for c in courses]
    count_by_course = (
        dict(
            db.query(Enrollment.course_id, func.count(Enrollment.id))
            .filter(Enrollment.course_id.in_(code_list), Enrollment.status == 1)
            .group_by(Enrollment.course_id)
            .all()
        )
        if code_list
        else {}
    )
    data = []
    for c in courses:
        data.append(
            {
                "course_id": c.course_code,
                "course_name": c.course_name,
                "credit": float(c.credit) if c.credit is not None else None,
                "hours": c.hours,
                "semester": c.semester,
                "student_count": count_by_course.get(c.course_code, 0),
            }
        )
    return ok(data)
