# -*- coding: utf-8 -*-
"""课堂互动 API：教师记录提问/评分/点名、随机点名、互动历史与统计；学生查本人互动"""
import datetime
import random

from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.api.deps import CurrentUser, get_db, require_roles
from app.api.notification import push as push_notif
from app.core.exception import BizError, ok
from app.models import ClassroomInteraction, Course, Enrollment, Student
from app.schemas.common import InteractionCreateReq

router = APIRouter(prefix="/api/interaction", tags=["interaction"])

VALID_TYPES = ("question", "rating", "random_pick")


def _get_owned_course(db, course_id: str, teacher_no: str) -> Course:
    course = db.query(Course).filter(Course.course_code == course_id).first()
    if course is None:
        raise BizError(404, "课程不存在")
    if course.teacher_id != teacher_no:
        raise BizError(403, "无权限操作该课程")
    return course


def _interaction_dict(r: ClassroomInteraction, student_name: str = None) -> dict:
    return {
        "id": r.id,
        "course_id": r.course_id,
        "student_id": r.student_id,
        "student_name": student_name,
        "interaction_type": r.interaction_type,
        "content": r.content,
        "score": r.score,
        "teacher_id": r.teacher_id,
        "lesson_date": r.lesson_date,
        "create_time": r.create_time,
    }


def _attach_names(db, rows) -> list:
    nos = {r.student_id for r in rows if r.student_id}
    names = {}
    if nos:
        names = dict(
            db.query(Student.student_no, Student.name)
            .filter(Student.student_no.in_(nos))
            .all()
        )
    return [
        _interaction_dict(r, names.get(r.student_id) if r.student_id else None)
        for r in rows
    ]


# ---------- 教师记录课堂互动（提问/评分/点名补录） ----------

@router.post("/")
def create_interaction(
    req: InteractionCreateReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    if req.interaction_type not in VALID_TYPES:
        raise BizError(400, "interaction_type 必须为 question/rating/random_pick")
    _get_owned_course(db, req.course_id, current.user.teacher_no)

    if req.interaction_type in ("question", "rating") and not req.student_id:
        raise BizError(400, "提问/评分互动必须指定学生")
    if req.interaction_type == "rating" and (
        req.score is None or not 1 <= req.score <= 5
    ):
        raise BizError(400, "评分互动的 score 必须为 1-5")
    if req.student_id:
        st = db.query(Student).filter(Student.student_no == req.student_id).first()
        if st is None:
            raise BizError(404, "学生不存在")

    rec = ClassroomInteraction(
        course_id=req.course_id,
        student_id=req.student_id,
        interaction_type=req.interaction_type,
        content=req.content,
        score=req.score,
        teacher_id=current.user.teacher_no,
        lesson_date=req.lesson_date or datetime.date.today(),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return ok(_interaction_dict(rec), message="互动记录已保存")


# ---------- 教师查互动历史 ----------

@router.get("/list")
def list_interactions(
    course_id: str = "",
    date: str = "",
    student_id: str = "",
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    q = db.query(ClassroomInteraction).filter(
        ClassroomInteraction.teacher_id == current.user.teacher_no
    )
    if course_id:
        _get_owned_course(db, course_id, current.user.teacher_no)
        q = q.filter(ClassroomInteraction.course_id == course_id)
    if date:
        try:
            d = datetime.date.fromisoformat(date)
        except ValueError:
            raise BizError(400, "日期格式错误，应为 YYYY-MM-DD")
        q = q.filter(ClassroomInteraction.lesson_date == d)
    if student_id:
        q = q.filter(ClassroomInteraction.student_id == student_id)
    rows = q.order_by(ClassroomInteraction.id.desc()).limit(500).all()
    return ok(_attach_names(db, rows))


# ---------- 教师随机点名 ----------

@router.get("/random-pick/{course_id}")
def random_pick(
    course_id: str,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    course = _get_owned_course(db, course_id, current.user.teacher_no)
    students = (
        db.query(Student.student_no, Student.name)
        .join(
            Enrollment,
            (Enrollment.student_id == Student.student_no)
            & (Enrollment.course_id == course_id)
            & (Enrollment.status == 1),
        )
        .all()
    )
    if not students:
        raise BizError(400, "该课程暂无选课学生")
    picked = random.choice(students)
    db.add(
        ClassroomInteraction(
            course_id=course_id,
            student_id=picked.student_no,
            interaction_type="random_pick",
            content="课堂随机点名",
            teacher_id=current.user.teacher_no,
            lesson_date=datetime.date.today(),
        )
    )
    db.commit()

    # ---- 站内消息：被点学生 + 同课其他学生（push 内部独立提交，不影响主流程）----
    course_name = course.course_name or course_id
    push_notif(
        db, picked.student_no, "student", "random_pick",
        "随机点名",
        f"你被点到名了！《{course_name}》课堂随机点名选中了你，请准备回答问题。",
        course_id=course_id,
    )
    for sno, _name in students:
        if sno == picked.student_no:
            continue
        push_notif(
            db, sno, "student", "random_pick",
            "随机点名",
            f"《{course_name}》本次随机点名结果：{picked.name}（{picked.student_no}）被点到。",
            course_id=course_id,
        )

    return ok(
        {"student_no": picked.student_no, "name": picked.name}, message="点名完成"
    )


# ---------- 学生：本人互动历史（提问/评分/被点记录） ----------

@router.get("/my")
def my_interactions(
    course_id: str = "",
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    sno = current.user.student_no
    q = db.query(ClassroomInteraction).filter(ClassroomInteraction.student_id == sno)
    if course_id:
        enrolled = (
            db.query(Enrollment)
            .filter(
                Enrollment.course_id == course_id,
                Enrollment.student_id == sno,
                Enrollment.status == 1,
            )
            .first()
        )
        if enrolled is None:
            raise BizError(403, "未选修该课程")
        q = q.filter(ClassroomInteraction.course_id == course_id)
    rows = q.order_by(ClassroomInteraction.id.desc()).limit(200).all()
    return ok(_attach_names(db, rows))


# ---------- 教师：互动统计 ----------

@router.get("/stats/{course_id}")
def interaction_stats(
    course_id: str,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    _get_owned_course(db, course_id, current.user.teacher_no)
    today = datetime.date.today()
    by_type = {}
    by_student = {}
    today_count = 0
    total = 0
    rows = (
        db.query(ClassroomInteraction)
        .filter(ClassroomInteraction.course_id == course_id)
        .all()
    )
    for r in rows:
        total += 1
        by_type[r.interaction_type] = by_type.get(r.interaction_type, 0) + 1
        if r.student_id:
            by_student[r.student_id] = by_student.get(r.student_id, 0) + 1
        if r.lesson_date == today:
            today_count += 1

    names = {}
    if by_student:
        names = dict(
            db.query(Student.student_no, Student.name)
            .filter(Student.student_no.in_(list(by_student.keys())))
            .all()
        )
    top10 = sorted(by_student.items(), key=lambda kv: kv[1], reverse=True)[:10]
    enrolled = (
        db.query(func.count(Enrollment.id))
        .filter(Enrollment.course_id == course_id, Enrollment.status == 1)
        .scalar()
    )
    return ok(
        {
            "course_id": course_id,
            "total": total,
            "enrolled_count": enrolled,
            "by_type": by_type,
            "today_count": today_count,
            "top_students": [
                {
                    "student_id": sno,
                    "name": names.get(sno),
                    "count": cnt,
                }
                for sno, cnt in top10
            ],
        }
    )
