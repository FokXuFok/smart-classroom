# -*- coding: utf-8 -*-
"""辅导员端 API：管辖班级、学生名单、学业预警、学生学业档案、整体概览"""
from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.api.deps import CurrentUser, get_db, require_roles
from app.core.exception import BizError, ok
from app.models import (
    AttendanceRecord,
    ClassInfo,
    ClassroomInteraction,
    Course,
    CounselorClass,
    GradeBook,
    Homework,
    Student,
)

router = APIRouter(prefix="/api/counselor", tags=["counselor"])

ATT_STATUS_CN = {0: "缺勤", 1: "正常", 2: "迟到", 3: "早退", 4: "请假"}

# 预警规则阈值
LOW_RATE_THRESHOLD = 0.8       # 出勤率预警线
LOW_RATE_MIN_RECORDS = 3       # 出勤率评估最少签到次数
ABSENT_THRESHOLD = 3           # 缺勤次数预警线
HOMEWORK_MIN_COUNT = 2         # 作业成绩评估最少作业数
HOMEWORK_GAP = 20              # 低于班级均分分差
RECENT_HOMEWORK = 3            # 取最近 N 次作业


def _my_class_ids(db, counselor_no: str) -> list:
    return [
        cid
        for (cid,) in db.query(CounselorClass.class_id)
        .filter(CounselorClass.counselor_id == counselor_no)
        .all()
    ]


def _my_students(db, counselor_no: str) -> list:
    """我辖班级全部学生 [(Student, class_name)]"""
    return (
        db.query(Student, ClassInfo.class_name)
        .join(
            CounselorClass,
            (CounselorClass.class_id == Student.class_id)
            & (CounselorClass.counselor_id == counselor_no),
        )
        .outerjoin(ClassInfo, ClassInfo.class_code == Student.class_id)
        .order_by(Student.class_id, Student.student_no)
        .all()
    )


def _attendance_stats(db, student_nos: list) -> dict:
    """出勤聚合：sno -> {total, attended(1/2/4), absent(0)}"""
    stats = {}
    if not student_nos:
        return stats
    rows = (
        db.query(
            AttendanceRecord.student_id,
            AttendanceRecord.status,
            func.count(AttendanceRecord.id),
        )
        .filter(AttendanceRecord.student_id.in_(student_nos))
        .group_by(AttendanceRecord.student_id, AttendanceRecord.status)
        .all()
    )
    for sno, status, cnt in rows:
        st = stats.setdefault(sno, {"total": 0, "attended": 0, "absent": 0})
        st["total"] += cnt
        if status in (1, 2, 4):
            st["attended"] += cnt
        if status == 0:
            st["absent"] += cnt
    return stats


def _homework_reason(db, sno: str):
    """最近 3 次作业均分 vs 班级均分；作业数>=2 才评估。

    返回 (student_avg, class_avg, reason|None)
    """
    records = (
        db.query(GradeBook)
        .filter(GradeBook.student_id == sno)
        .order_by(GradeBook.judge_time.asc(), GradeBook.id.asc())
        .all()
    )
    if len(records) < HOMEWORK_MIN_COUNT:
        return None, None, None
    recent = records[-RECENT_HOMEWORK:]
    scores = [float(r.score) for r in recent if r.score is not None]
    if not scores:
        return None, None, None
    student_avg = sum(scores) / len(scores)
    hw_ids = [r.homework_id for r in recent]
    class_avg = (
        db.query(func.avg(GradeBook.score))
        .filter(GradeBook.homework_id.in_(hw_ids))
        .scalar()
    )
    if class_avg is None:
        return student_avg, None, None
    class_avg = float(class_avg)
    if student_avg < class_avg - HOMEWORK_GAP:
        return (
            student_avg,
            class_avg,
            f"最近{len(recent)}次作业均分{student_avg:.1f}，低于班级均分{class_avg:.1f}超过{HOMEWORK_GAP}分",
        )
    return student_avg, class_avg, None


def _compute_warnings(db, counselor_no: str) -> list:
    """逐个学生计算预警：返回含 reasons 的列表（仅含触发预警的学生）"""
    students = _my_students(db, counselor_no)
    if not students:
        return []
    att = _attendance_stats(db, [s.student_no for s, _ in students])

    result = []
    for st, class_name in students:
        sno = st.student_no
        a = att.get(sno) or {"total": 0, "attended": 0, "absent": 0}
        total = a["total"]
        rate = a["attended"] / total if total else None
        reasons = []
        # 出勤类规则仅在有签到记录时评估；作业规则无条件评估（规则解耦）
        if total and rate < LOW_RATE_THRESHOLD and total >= LOW_RATE_MIN_RECORDS:
            reasons.append(f"出勤率仅{rate:.0%}（低于{LOW_RATE_THRESHOLD:.0%}）")
        if total and a["absent"] >= ABSENT_THRESHOLD:
            reasons.append(f"累计缺勤{a['absent']}次")
        homework_avg, class_avg, hw_reason = _homework_reason(db, sno)
        if hw_reason:
            reasons.append(hw_reason)
        if not reasons:
            continue
        result.append(
            {
                "student_no": sno,
                "name": st.name,
                "class_name": class_name,
                "attendance_rate": round(rate, 4) if rate is not None else None,
                "absent_count": a["absent"],
                "homework_avg": round(homework_avg, 2) if homework_avg is not None else None,
                "class_avg": round(class_avg, 2) if class_avg is not None else None,
                "reasons": reasons,
            }
        )
    result.sort(key=lambda x: -len(x["reasons"]))
    return result


# ---------- 我管辖的班级 ----------

@router.get("/classes")
def my_classes(
    current: CurrentUser = Depends(require_roles("counselor")),
    db=Depends(get_db),
):
    rows = (
        db.query(ClassInfo)
        .join(
            CounselorClass, CounselorClass.class_id == ClassInfo.class_code
        )
        .filter(CounselorClass.counselor_id == current.user.counselor_no)
        .order_by(ClassInfo.class_code)
        .all()
    )
    data = []
    if rows:
        code_list = [c.class_code for c in rows]
        count_by_class = dict(
            db.query(Student.class_id, func.count(Student.student_no))
            .filter(Student.class_id.in_(code_list))
            .group_by(Student.class_id)
            .all()
        )
    else:
        count_by_class = {}
    for c in rows:
        data.append(
            {
                "class_id": c.class_code,
                "class_name": c.class_name,
                "grade": c.grade,
                "major": c.major,
                "department": c.department,
                "student_count": count_by_class.get(c.class_code, 0),
            }
        )
    return ok(data)


# ---------- 班级学生名单 ----------

@router.get("/students")
def class_students(
    class_id: str,
    current: CurrentUser = Depends(require_roles("counselor")),
    db=Depends(get_db),
):
    if class_id not in _my_class_ids(db, current.user.counselor_no):
        raise BizError(403, "该班级不在您管辖范围")
    rows = (
        db.query(Student)
        .filter(Student.class_id == class_id)
        .order_by(Student.student_no)
        .all()
    )
    return ok(
        [
            {
                "student_no": s.student_no,
                "name": s.name,
                "gender": s.gender,
                "phone": s.phone,
                "email": s.email,
                "status": s.status,
                "class_id": s.class_id,
            }
            for s in rows
        ]
    )


# ---------- 学业预警 ----------

@router.get("/warnings")
def warnings(
    current: CurrentUser = Depends(require_roles("counselor")),
    db=Depends(get_db),
):
    return ok(_compute_warnings(db, current.user.counselor_no))


# ---------- 学生学业档案 ----------

@router.get("/student/{student_no}/profile")
def student_profile(
    student_no: str,
    current: CurrentUser = Depends(require_roles("counselor")),
    db=Depends(get_db),
):
    row = (
        db.query(Student, ClassInfo.class_name)
        .outerjoin(ClassInfo, ClassInfo.class_code == Student.class_id)
        .filter(Student.student_no == student_no)
        .first()
    )
    if row is None:
        raise BizError(404, "学生不存在")
    st, class_name = row
    if st.class_id not in _my_class_ids(db, current.user.counselor_no):
        raise BizError(403, "该学生不在您管辖班级")

    # ---- 出勤统计 ----
    recs = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.student_id == student_no)
        .order_by(AttendanceRecord.id.desc())
        .all()
    )
    status_count = {}
    for r in recs:
        status_count[r.status] = status_count.get(r.status, 0) + 1
    attended = sum(status_count.get(k, 0) for k in (1, 2, 4))
    rate = round(attended / len(recs), 4) if recs else None
    recent = recs[:10]
    course_names = {}
    if recent:
        course_names = dict(
            db.query(Course.course_code, Course.course_name)
            .filter(Course.course_code.in_([r.course_id for r in recent]))
            .all()
        )
    recent_list = [
        {
            "id": r.id,
            "course_id": r.course_id,
            "course_name": course_names.get(r.course_id),
            "attendance_date": r.attendance_date,
            "status": r.status,
            "status_cn": ATT_STATUS_CN.get(r.status, str(r.status)),
            "check_in_time": r.check_in_time,
        }
        for r in recent
    ]

    # ---- 成绩趋势 ----
    grades = (
        db.query(GradeBook, Homework.title)
        .outerjoin(Homework, Homework.id == GradeBook.homework_id)
        .filter(GradeBook.student_id == student_no)
        .order_by(GradeBook.judge_time.asc(), GradeBook.id.asc())
        .all()
    )
    grade_list = [
        {
            "homework_id": gb.homework_id,
            "homework_title": title,
            "course_id": gb.course_id,
            "score": gb.score,
            "judge_time": gb.judge_time,
        }
        for gb, title in grades
    ]

    # ---- 互动记录（近 20 条） ----
    interactions = (
        db.query(ClassroomInteraction)
        .filter(ClassroomInteraction.student_id == student_no)
        .order_by(ClassroomInteraction.id.desc())
        .limit(20)
        .all()
    )
    interaction_list = [
        {
            "id": r.id,
            "course_id": r.course_id,
            "interaction_type": r.interaction_type,
            "content": r.content,
            "score": r.score,
            "lesson_date": r.lesson_date,
            "create_time": r.create_time,
        }
        for r in interactions
    ]

    return ok(
        {
            "student": {
                "student_no": st.student_no,
                "name": st.name,
                "gender": st.gender,
                "phone": st.phone,
                "email": st.email,
                "status": st.status,
                "class_id": st.class_id,
                "class_name": class_name,
            },
            "attendance": {
                "total": len(recs),
                "status_count": {
                    ATT_STATUS_CN.get(k, str(k)): v
                    for k, v in status_count.items()
                },
                "attendance_rate": rate,
                "recent": recent_list,
            },
            "grades": grade_list,
            "interactions": interaction_list,
        }
    )


# ---------- 我辖班级整体概览 ----------

@router.get("/stat")
def counselor_stat(
    current: CurrentUser = Depends(require_roles("counselor")),
    db=Depends(get_db),
):
    counselor_no = current.user.counselor_no
    students = _my_students(db, counselor_no)
    nos = [s.student_no for s, _ in students]
    att = _attendance_stats(db, nos)

    rates = [a["attended"] / a["total"] for a in att.values() if a["total"]]
    avg_rate = round(sum(rates) / len(rates), 4) if rates else None
    warning_rows = _compute_warnings(db, counselor_no)

    return ok(
        {
            "class_count": len(_my_class_ids(db, counselor_no)),
            "student_total": len(students),
            "avg_attendance_rate": avg_rate,
            "warning_count": len(warning_rows),
        }
    )
