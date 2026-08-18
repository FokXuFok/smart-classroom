# -*- coding: utf-8 -*-
"""学生端 API：签到提交（人脸+定位+指纹预留）、人脸注册、请假申请、历史与统计"""
import base64
import datetime
import json

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

import config
from app.api.deps import CurrentUser, get_db, require_roles
from app.core import face_engine, fingerprint
from app.core.exception import BizError, ok
from app.core.geofence import within_range
from app.core.judge.service import judge_submission
from app.core.logger import get_logger
from app.models import (
    AttendanceRecord,
    CheckinSession,
    Course,
    Enrollment,
    GradeBook,
    Homework,
    SubmissionRecord,
    TestCase,
)
from app.schemas.checkin import ApplyCheckinReq, FaceRegisterReq, SubmitCheckinReq
from app.schemas.homework import SubmitCodeReq

router = APIRouter(prefix="/api/student", tags=["student-checkin"])

logger = get_logger("app.checkin")

ATT_STATUS_CN = {0: "缺勤", 1: "正常", 2: "迟到", 3: "早退", 4: "请假"}


def _decode_b64_image(image_b64: str):
    """base64 图片 → bytes；兼容 data URI 前缀；失败返回 None"""
    try:
        if image_b64.startswith("data:"):
            image_b64 = image_b64.split(",", 1)[-1]
        return base64.b64decode(image_b64)
    except Exception:
        return None


# ---------- 我的课程（含出勤率） ----------

@router.get("/courses")
def my_courses(
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    courses = (
        db.query(Course)
        .join(
            Enrollment,
            (Enrollment.course_id == Course.course_code)
            & (Enrollment.student_id == sno)
            & (Enrollment.status == 1),
        )
        .filter(Course.status == 1)
        .order_by(Course.course_code)
        .all()
    )
    data = []
    if courses:
        code_list = [c.course_code for c in courses]
        # 批量聚合：每课已发起签到数
        session_by_course = dict(
            db.query(
                CheckinSession.course_id, func.count(CheckinSession.id)
            )
            .filter(CheckinSession.course_id.in_(code_list))
            .group_by(CheckinSession.course_id)
            .all()
        )
        # 批量聚合：每课本人有效出勤数
        attended_by_course = dict(
            db.query(
                AttendanceRecord.course_id, func.count(AttendanceRecord.id)
            )
            .filter(
                AttendanceRecord.course_id.in_(code_list),
                AttendanceRecord.student_id == sno,
                AttendanceRecord.status.in_([1, 2]),
            )
            .group_by(AttendanceRecord.course_id)
            .all()
        )
    else:
        session_by_course, attended_by_course = {}, {}
    for c in courses:
        total_sessions = session_by_course.get(c.course_code, 0)
        attended = attended_by_course.get(c.course_code, 0)
        data.append(
            {
                "course_id": c.course_code,
                "course_name": c.course_name,
                "credit": float(c.credit) if c.credit is not None else None,
                "hours": c.hours,
                "semester": c.semester,
                "total_sessions": total_sessions,
                "attended": attended,
                "attendance_rate": (
                    round(attended / total_sessions, 4) if total_sessions else None
                ),
            }
        )
    return ok(data)


# ---------- 进行中的签到会话 ----------

@router.get("/checkin/active")
def active_sessions(
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    now = datetime.datetime.now()
    sessions = (
        db.query(CheckinSession)
        .join(
            Enrollment,
            (Enrollment.course_id == CheckinSession.course_id)
            & (Enrollment.student_id == sno)
            & (Enrollment.status == 1),
        )
        .filter(CheckinSession.status == 1)
        .all()
    )
    data = []
    for s in sessions:
        deadline = s.create_time + datetime.timedelta(
            minutes=s.duration_minutes or 5
        )
        if deadline <= now:  # 已过期：顺手关闭
            s.status = 0
            s.end_time = now
            continue
        data.append(
            {
                "id": s.id,
                "course_id": s.course_id,
                "teacher_lat": s.teacher_lat,
                "teacher_lng": s.teacher_lng,
                "range_meters": s.range_meters,
                "duration_minutes": s.duration_minutes,
                "create_time": s.create_time,
                "deadline": deadline,
                "remaining_seconds": int((deadline - now).total_seconds()),
            }
        )
    db.commit()
    return ok(data)


# ---------- 签到提交（核心） ----------

@router.post("/checkin/submit")
def submit_checkin(
    req: SubmitCheckinReq,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    now = datetime.datetime.now()

    # 1) 会话存在、进行中且未过期
    session = (
        db.query(CheckinSession).filter(CheckinSession.id == req.session_id).first()
    )
    if session is None:
        raise BizError(404, "签到会话不存在")
    if session.status != 1:
        raise BizError(2006, "签到会话已结束")
    deadline = session.create_time + datetime.timedelta(
        minutes=session.duration_minutes or 5
    )
    if deadline <= now:
        session.status = 0
        session.end_time = now
        db.commit()
        raise BizError(2006, "签到会话已结束")

    # 2) 选课校验
    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == session.course_id,
            Enrollment.student_id == sno,
            Enrollment.status == 1,
        )
        .first()
    )
    if enrolled is None:
        raise BizError(403, "未选该课程，无法签到")

    # 3) 重复签到
    exists = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.student_id == sno,
        )
        .first()
    )
    if exists is not None:
        raise BizError(2005, "重复签到，本次会话已提交过")

    # 4) 人脸模板
    student = current.user
    if not student.face_template:
        raise BizError(2001, "人脸未注册，请先到人脸注册页面上传照片")

    # 5) 地理围栏
    in_range, dist = within_range(
        session.teacher_lat,
        session.teacher_lng,
        req.lat,
        req.lng,
        session.range_meters,
    )
    if not in_range:
        if dist >= 0:
            logger.warning(
                "签到被拒(超出范围) student=%s session=%s course=%s 距离=%dm 限=%dm",
                sno, session.id, session.course_id, round(dist), session.range_meters,
            )
            raise BizError(
                2003,
                f"超出签到范围（距离签到点 {round(dist)} 米，"
                f"允许范围 {session.range_meters} 米）",
            )
        logger.warning(
            "签到被拒(无定位) student=%s session=%s course=%s",
            sno, session.id, session.course_id,
        )
        raise BizError(2003, "未获取到定位信息，无法签到")

    # 6) 人脸检测与嵌入
    eng = face_engine.get_engine()
    embedding, _face = eng.embed_b64_best(req.image_b64)
    if embedding is None:
        logger.warning(
            "签到被拒(未检出人脸) student=%s session=%s course=%s",
            sno, session.id, session.course_id,
        )
        raise BizError(400, "未检测到人脸，请正对摄像头重试")

    # 7) 相似度比对：不足则转人工复核
    sim = eng.compare_with_template(bytes(student.face_template), embedding)
    if sim < config.FACE_SIM_THRESHOLD:
        db.add(
            AttendanceRecord(
                course_id=session.course_id,
                student_id=sno,
                attendance_date=datetime.date.today(),
                status=0,
                check_in_time=now,
                check_in_type=1,
                location=f"{req.lat},{req.lng}",
                similarity1=round(float(sim), 4),
                session_id=session.id,
                review_status=1,
                review_remark=f"相似度不足({sim:.2f})，待人工复核",
            )
        )
        db.commit()
        logger.warning(
            "签到转人工复核(相似度不足) student=%s session=%s course=%s sim=%.3f 阈值=%.2f",
            sno, session.id, session.course_id, sim, config.FACE_SIM_THRESHOLD,
        )
        raise BizError(2002, f"人脸相似度不足({sim:.2f})，已提交人工复核")

    # 8) 指纹核验（预留，不阻断）
    fp = fingerprint.verify(sno, req.fingerprint)

    # 9) 两帧活体（可选）
    if req.image_b64_2:
        live = eng.liveness_two_frames(req.image_b64, req.image_b64_2)
        is_live = 1 if live.get("passed") else 0
    else:
        live = {"passed": True, "note": "未采集第二帧"}
        is_live = 1

    # 10) 正常 / 迟到
    late_delta = datetime.timedelta(minutes=config.LATE_MINUTES)
    status = 1 if (now - session.create_time) <= late_delta else 2

    # 11) 落库 + 保存自拍
    location = f"{req.lat},{req.lng}"
    rec = AttendanceRecord(
        course_id=session.course_id,
        student_id=sno,
        attendance_date=datetime.date.today(),
        status=status,
        check_in_time=now,
        check_in_type=1,
        location=location,
        similarity1=round(float(sim), 4),
        is_liveness_passed=is_live,
        session_id=session.id,
    )
    try:
        checkin_dir = config.UPLOAD_DIR / "checkin"
        checkin_dir.mkdir(parents=True, exist_ok=True)
        raw = _decode_b64_image(req.image_b64)
        if raw:
            (checkin_dir / f"{sno}_{session.id}.jpg").write_bytes(raw)
            rec.student_image_url = f"/uploads/checkin/{sno}_{session.id}.jpg"
    except Exception:
        pass
    db.add(rec)
    try:
        db.commit()
    except IntegrityError:
        # uk_session_student 并发兜底：另一请求已插入该会话记录
        db.rollback()
        raise BizError(2005, "该会话已签到，请勿重复提交")
    db.refresh(rec)
    logger.info(
        "签到成功 student=%s session=%s course=%s status=%s(%s) sim=%.3f 距离=%dm 活体=%s",
        sno, session.id, session.course_id, status, ATT_STATUS_CN.get(status),
        sim, round(dist), is_live,
    )

    return ok(
        {
            "record_id": rec.id,
            "session_id": session.id,
            "status": status,
            "status_cn": ATT_STATUS_CN.get(status),
            "similarity": round(float(sim), 4),
            "distance_m": round(dist),
            "fingerprint": fp,
            "liveness": live,
        },
        message="签到成功",
    )


# ---------- 人脸注册 ----------

@router.post("/face/register")
def face_register(
    req: FaceRegisterReq,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    student = current.user
    if student.face_template and student.face_regen_allowed != 1:
        raise BizError(403, "人脸已注册，如需更换请联系教师授权")

    eng = face_engine.get_engine()
    embedding, _face = eng.embed_b64_best(req.image_b64)
    if embedding is None:
        raise BizError(400, "未检测到人脸，请正对摄像头重试")

    student.face_template = eng.embedding_to_bytes(embedding)
    student.face_regen_allowed = 0
    face_image_url = f"/uploads/face/{student.student_no}.jpg"
    try:
        face_dir = config.UPLOAD_DIR / "face"
        face_dir.mkdir(parents=True, exist_ok=True)
        raw = _decode_b64_image(req.image_b64)
        if raw:
            (face_dir / f"{student.student_no}.jpg").write_bytes(raw)
    except Exception:
        pass
    student.face_image_url = face_image_url
    db.commit()
    logger.info("人脸注册成功 student=%s", student.student_no)
    return ok(
        {"student_no": student.student_no, "face_image_url": face_image_url},
        message="人脸注册成功",
    )


# ---------- 签到历史 ----------

@router.get("/checkin/history")
def checkin_history(
    course_id: str = "",
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    q = db.query(AttendanceRecord).filter(AttendanceRecord.student_id == sno)
    if course_id:
        q = q.filter(AttendanceRecord.course_id == course_id)
    recs = q.order_by(AttendanceRecord.id.desc()).all()
    data = [
        {
            "id": r.id,
            "course_id": r.course_id,
            "attendance_date": r.attendance_date,
            "status": r.status,
            "status_cn": ATT_STATUS_CN.get(r.status, str(r.status)),
            "check_in_time": r.check_in_time,
            "check_in_type": r.check_in_type,
            "similarity1": float(r.similarity1) if r.similarity1 is not None else None,
            "review_status": r.review_status,
            "session_id": r.session_id,
        }
        for r in recs
    ]
    return ok(data)


# ---------- 请假/补签申请 ----------

@router.post("/checkin/apply")
def apply_checkin(
    req: ApplyCheckinReq,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    session = (
        db.query(CheckinSession).filter(CheckinSession.id == req.session_id).first()
    )
    if session is None:
        raise BizError(404, "签到会话不存在")

    # 选课校验：只能对本人所选课程的会话申请请假
    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == session.course_id,
            Enrollment.student_id == sno,
            Enrollment.status == 1,
        )
        .first()
    )
    if enrolled is None:
        raise BizError(403, "未选修该课程，无法申请")

    exists = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.session_id == session.id,
            AttendanceRecord.student_id == sno,
        )
        .first()
    )
    if exists is not None:
        raise BizError(2005, "该会话已有签到记录，无法申请请假/补签")

    rec = AttendanceRecord(
        course_id=session.course_id,
        student_id=sno,
        attendance_date=datetime.date.today(),
        status=4,
        review_status=1,
        review_remark=req.reason,
        session_id=session.id,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return ok({"id": rec.id, "status": ATT_STATUS_CN[4]}, message="申请已提交，待教师审核")


# ---------- 出勤统计 ----------

@router.get("/attendance/stats")
def attendance_stats(
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    rows = dict(
        db.query(AttendanceRecord.status, func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.student_id == sno)
        .group_by(AttendanceRecord.status)
        .all()
    )
    detail = {ATT_STATUS_CN[k]: v for k, v in rows.items()}
    return ok({"total": sum(rows.values()), "detail": detail})


# =====================================================================
# 以下为编程作业学生端点（追加，不改动上方签到模块）
# =====================================================================

SUBMIT_STATUS_CN = {0: "待评测", 1: "已评测", 2: "已批改"}


def _enrolled(db, course_id: str, sno: str) -> bool:
    return (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == course_id,
            Enrollment.student_id == sno,
            Enrollment.status == 1,
        )
        .first()
        is not None
    )


# ---------- 我的作业列表（/homework/list 须先于 /homework/{id} 注册） ----------

@router.get("/homework/list")
def my_homework_list(
    course_id: str = "",
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    q = (
        db.query(Homework)
        .join(
            Enrollment,
            (Enrollment.course_id == Homework.course_id)
            & (Enrollment.student_id == sno)
            & (Enrollment.status == 1),
        )
        .filter(Homework.status == 1)
    )
    if course_id:
        q = q.filter(Homework.course_id == course_id)
    homework_list = q.order_by(Homework.id.desc()).all()

    data = []
    for hw in homework_list:
        gb = (
            db.query(GradeBook)
            .filter(
                GradeBook.homework_id == hw.id, GradeBook.student_id == sno
            )
            .first()
        )
        data.append(
            {
                "id": hw.id,
                "course_id": hw.course_id,
                "title": hw.title,
                "programming_language": hw.programming_language,
                "max_score": hw.max_score,
                "deadline": hw.deadline,
                "allow_late_submit": hw.allow_late_submit,
                "my_best_score": gb.score if gb else None,
                "my_submit_count": gb.submit_count if gb else 0,
            }
        )
    return ok(data)


# ---------- 作业详情（隐藏非公开用例的输入/期望输出） ----------

@router.get("/homework/{homework_id}")
def homework_detail(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    hw = db.get(Homework, homework_id)
    if hw is None:
        raise BizError(404, "作业不存在")
    if not _enrolled(db, hw.course_id, sno):
        raise BizError(403, "未选修该课程，无法查看作业")
    if hw.status == 0:
        raise BizError(403, "作业尚未发布")

    cases = (
        db.query(TestCase)
        .filter(TestCase.homework_id == hw.id)
        .order_by(TestCase.order_num, TestCase.id)
        .all()
    )
    data = {
        "id": hw.id,
        "course_id": hw.course_id,
        "title": hw.title,
        "description": hw.description,
        "programming_language": hw.programming_language,
        "max_score": hw.max_score,
        "deadline": hw.deadline,
        "allow_late_submit": hw.allow_late_submit,
        "test_cases": [],
    }
    for c in cases:
        if c.is_public:
            data["test_cases"].append(
                {
                    "id": c.id,
                    "name": c.name,
                    "is_public": c.is_public,
                    "score_weight": c.score_weight,
                    "test_input": c.test_input,
                    "expected_output": c.expected_output,
                }
            )
        else:  # 隐藏用例：只返回 name/weight
            data["test_cases"].append(
                {
                    "id": c.id,
                    "name": c.name,
                    "is_public": c.is_public,
                    "score_weight": c.score_weight,
                }
            )
    return ok(data)


# ---------- 提交代码（写库后后台评测，立即返回 submission_id） ----------

@router.post("/homework/{homework_id}/submit")
def submit_homework(
    homework_id: int,
    req: SubmitCodeReq,
    background_tasks: BackgroundTasks,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    hw = db.get(Homework, homework_id)
    if hw is None:
        raise BizError(404, "作业不存在")
    if not _enrolled(db, hw.course_id, sno):
        raise BizError(403, "未选修该课程，无法提交作业")
    if hw.status != 1:
        raise BizError(400, "作业不在可提交状态")

    now = datetime.datetime.now()
    if (
        hw.deadline is not None
        and now > hw.deadline
        and not hw.allow_late_submit
    ):
        raise BizError(3002, "作业已截止，禁止提交")

    rec = SubmissionRecord(
        homework_id=hw.id,
        student_id=sno,
        course_id=hw.course_id,
        submitted_code=req.code,
        submit_time=now,
        status=0,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    background_tasks.add_task(judge_submission, rec.id)
    return ok(
        {"submission_id": rec.id, "status": rec.status},
        message="提交成功，正在评测",
    )


# ---------- 我的提交历史 ----------

@router.get("/homework/{homework_id}/my")
def my_submissions(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    hw = db.get(Homework, homework_id)
    if hw is None:
        raise BizError(404, "作业不存在")
    if not _enrolled(db, hw.course_id, sno):
        raise BizError(403, "未选修该课程，无法查看作业")

    # 反馈开放策略：教师提前开放，或已过截止时间
    now = datetime.datetime.now()
    feedback_open = bool(hw.feedback_visible) or (
        hw.deadline is not None and now >= hw.deadline
    )

    recs = (
        db.query(SubmissionRecord)
        .filter(
            SubmissionRecord.homework_id == hw.id,
            SubmissionRecord.student_id == sno,
        )
        .order_by(SubmissionRecord.id.desc())
        .all()
    )
    # 隐藏用例防泄露：{case_id: is_public}，非公开用例不回传 expected/stdout
    case_public = {
        c.id: bool(c.is_public)
        for c in db.query(TestCase).filter(TestCase.homework_id == hw.id).all()
    }
    data = []
    for r in recs:
        try:
            test_results = json.loads(r.test_results) if r.test_results else []
        except (ValueError, TypeError):
            test_results = []
        for item in test_results:
            if isinstance(item, dict) and not case_public.get(item.get("case_id")):
                item.pop("expected", None)
                item.pop("stdout", None)
        data.append(
            {
                "id": r.id,
                "submit_time": r.submit_time,
                "judge_time": r.judge_time,
                "status": r.status,
                "status_cn": SUBMIT_STATUS_CN.get(r.status, str(r.status)),
                "score": r.score,
                "compile_error": r.compile_error,
                "test_results": test_results,
                "ai_feedback": (
                    r.ai_feedback
                    if feedback_open and r.ai_feedback
                    else None
                ),
                "ai_feedback_hint": (
                    None if feedback_open else "AI 反馈尚未开放（截止后或教师开放后可见）"
                ),
            }
        )
    return ok(data)
