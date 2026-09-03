# -*- coding: utf-8 -*-
"""教师端作业 API：作业 CRUD、提交列表、成绩簿、Excel 导出、查重、重评、反馈开放"""
from io import BytesIO
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func

from app.api.deps import CurrentUser, get_db, require_roles
from app.api.notification import push_many
from app.core.exception import BizError, ok
from app.core.judge.service import check_homework_similarity, judge_submission
from app.models import (
    Course,
    Enrollment,
    GradeBook,
    Homework,
    Student,
    SubmissionRecord,
    TestCase,
)
from app.schemas.homework import HomeworkCreateReq, HomeworkUpdateReq

router = APIRouter(prefix="/api/homework", tags=["homework-teacher"])

SUBMIT_STATUS_CN = {0: "待评测", 1: "已评测", 2: "已批改"}


def _get_owned_homework(db, homework_id: int, teacher_no: str) -> Homework:
    hw = db.get(Homework, homework_id)
    if hw is None:
        raise BizError(404, "作业不存在")
    if hw.teacher_id != teacher_no:
        raise BizError(403, "无权限操作该作业")
    return hw


def _case_dict(c: TestCase, public_only: bool = False) -> dict:
    d = {
        "id": c.id,
        "name": c.name,
        "score_weight": c.score_weight,
        "is_public": c.is_public,
        "time_limit": c.time_limit,
        "memory_limit": c.memory_limit,
        "order_num": c.order_num,
    }
    if not public_only or c.is_public:
        d["test_input"] = c.test_input
        d["expected_output"] = c.expected_output
    return d


def _rebuild_cases(db, homework_id: int, cases: list) -> None:
    """test_cases 传入则全删重建"""
    db.query(TestCase).filter(TestCase.homework_id == homework_id).delete(
        synchronize_session=False
    )
    for idx, tc in enumerate(cases):
        db.add(
            TestCase(
                homework_id=homework_id,
                name=tc.name,
                test_input=tc.test_input,
                expected_output=tc.expected_output,
                score_weight=tc.score_weight,
                is_public=1 if tc.is_public else 0,
                order_num=idx,
            )
        )


# ---------- 创建（/list 必须先于 /{id} 注册） ----------

@router.post("/")
def create_homework(
    req: HomeworkCreateReq,
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

    hw = Homework(
        course_id=req.course_id,
        teacher_id=current.user.teacher_no,
        title=req.title,
        description=req.description,
        programming_language=req.programming_language,
        max_score=req.max_score,
        deadline=req.deadline,
        allow_late_submit=1 if req.allow_late_submit else 0,
        status=1,
    )
    db.add(hw)
    db.commit()
    db.refresh(hw)
    _rebuild_cases(db, hw.id, req.test_cases)
    db.commit()
    # 通知钩子：给选课学生批量发作业发布通知（push_many 单事务写入）
    enrolled_nos = [
        sno
        for (sno,) in (
            db.query(Student.student_no)
            .join(
                Enrollment,
                (Enrollment.student_id == Student.student_no)
                & (Enrollment.course_id == req.course_id)
                & (Enrollment.status == 1),
            )
            .all()
        )
    ]
    push_many(
        db,
        [
            (
                sno,
                "student",
                "homework_publish",
                f"新作业：{hw.title}",
                f"《{course.course_name}》发布了新作业「{hw.title}」，请及时完成。",
                hw.id,
                hw.course_id,
            )
            for sno in enrolled_nos
        ],
    )
    return ok({"homework_id": hw.id}, message="作业创建成功")


@router.get("/list")
def list_homework(
    course_id: str = "",
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    q = db.query(Homework).filter(Homework.teacher_id == current.user.teacher_no)
    if course_id:
        q = q.filter(Homework.course_id == course_id)
    homework_list = q.order_by(Homework.id.desc()).all()

    data = []
    for hw in homework_list:
        submit_count = (
            db.query(func.count(SubmissionRecord.id))
            .filter(SubmissionRecord.homework_id == hw.id)
            .scalar()
        )
        student_count = (
            db.query(func.count(func.distinct(SubmissionRecord.student_id)))
            .filter(SubmissionRecord.homework_id == hw.id)
            .scalar()
        )
        case_count = (
            db.query(func.count(TestCase.id))
            .filter(TestCase.homework_id == hw.id)
            .scalar()
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
                "status": hw.status,
                "feedback_visible": hw.feedback_visible,
                "test_case_count": case_count,
                "submit_count": submit_count,
                "student_count": student_count,
            }
        )
    return ok(data)


# ---------- 详情 / 更新 / 删除 ----------

@router.get("/{homework_id}")
def homework_detail(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    cases = (
        db.query(TestCase)
        .filter(TestCase.homework_id == hw.id)
        .order_by(TestCase.order_num, TestCase.id)
        .all()
    )
    return ok(
        {
            "id": hw.id,
            "course_id": hw.course_id,
            "teacher_id": hw.teacher_id,
            "title": hw.title,
            "description": hw.description,
            "programming_language": hw.programming_language,
            "max_score": hw.max_score,
            "deadline": hw.deadline,
            "allow_late_submit": hw.allow_late_submit,
            "status": hw.status,
            "feedback_visible": hw.feedback_visible,
            "test_cases": [_case_dict(c) for c in cases],
        }
    )


@router.put("/{homework_id}")
def update_homework(
    homework_id: int,
    req: HomeworkUpdateReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    for field in (
        "title",
        "description",
        "programming_language",
        "max_score",
        "deadline",
        "status",
    ):
        value = getattr(req, field)
        if value is not None:
            setattr(hw, field, value)
    if req.allow_late_submit is not None:
        hw.allow_late_submit = 1 if req.allow_late_submit else 0
    if req.test_cases is not None:
        _rebuild_cases(db, hw.id, req.test_cases)
    db.commit()
    return ok({"homework_id": hw.id}, message="作业已更新")


@router.delete("/{homework_id}")
def delete_homework(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    submit_count = (
        db.query(func.count(SubmissionRecord.id))
        .filter(SubmissionRecord.homework_id == hw.id)
        .scalar()
    )
    if submit_count:
        raise BizError(400, f"该作业已有 {submit_count} 条提交记录，不可删除")
    db.query(TestCase).filter(TestCase.homework_id == hw.id).delete(
        synchronize_session=False
    )
    db.delete(hw)
    db.commit()
    return ok({"homework_id": homework_id}, message="作业已删除")


# ---------- 提交列表 / 成绩簿 ----------

@router.get("/{homework_id}/submissions")
def homework_submissions(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    rows = (
        db.query(SubmissionRecord, Student)
        .outerjoin(Student, Student.student_no == SubmissionRecord.student_id)
        .filter(SubmissionRecord.homework_id == hw.id)
        .order_by(SubmissionRecord.id.desc())
        .all()
    )
    data = [
        {
            "id": sub.id,
            "student_id": sub.student_id,
            "student_name": st.name if st else None,
            "submit_time": sub.submit_time,
            "judge_time": sub.judge_time,
            "status": sub.status,
            "status_cn": SUBMIT_STATUS_CN.get(sub.status, str(sub.status)),
            "score": sub.score,
            "compile_error": sub.compile_error,
            "ai_feedback": (
                (sub.ai_feedback or "")[:200] if sub.ai_feedback else None
            ),
        }
        for sub, st in rows
    ]
    return ok(data)


def _gradebook_rows(db, hw: Homework) -> list:
    """成绩册行（成绩册页与 Excel 导出共用）"""
    rows = (
        db.query(GradeBook, Student)
        .outerjoin(
            Student,
            # grade_book 与 student 表字符序不一致（unicode_ci vs 0900_ai_ci），
            # 显式 COLLATE 对齐，否则 MySQL 报 Illegal mix of collations
            Student.student_no
            == GradeBook.student_id.collate("utf8mb4_0900_ai_ci"),
        )
        .filter(GradeBook.homework_id == hw.id)
        .order_by(Student.student_no)
        .all()
    )
    return [
        {
            "student_id": gb.student_id,
            "student_name": st.name if st else None,
            "score": gb.score,
            "submit_count": gb.submit_count,
            "judge_time": gb.judge_time,
        }
        for gb, st in rows
    ]


@router.get("/{homework_id}/gradebook")
def homework_gradebook(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    rows = _gradebook_rows(db, hw)
    return ok(rows)


# ---------- 成绩册导出 Excel ----------

@router.get("/{homework_id}/gradebook/export")
def gradebook_export(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    """作业成绩册导出 .xlsx（浏览器同源 cookie 下载）"""
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    rows = _gradebook_rows(db, hw)

    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "成绩册"
    ws.append(["学号", "姓名", "成绩", "提交次数", "最近评测时间", "满分"])
    for r in rows:
        ws.append([
            r["student_id"],
            r["student_name"] or "",
            float(r["score"]) if r["score"] is not None else "",
            r["submit_count"],
            str(r["judge_time"] or ""),
            hw.max_score,
        ])
    for col, width in zip("ABCDEF", (14, 10, 8, 10, 20, 8)):
        ws.column_dimensions[col].width = width

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = quote(f"成绩册_{hw.course_id}_{hw.title}.xlsx")
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


# ---------- 查重 / 重评 / 开放反馈 ----------

@router.post("/{homework_id}/similarity")
def homework_similarity(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    pairs = check_homework_similarity(hw.id)
    return ok(pairs, message=f"查重完成，命中 {len(pairs)} 对疑似抄袭")


@router.post("/{homework_id}/rejudge")
def homework_rejudge(
    homework_id: int,
    background_tasks: BackgroundTasks,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    sub_ids = [
        sid
        for (sid,) in db.query(SubmissionRecord.id).filter(
            SubmissionRecord.homework_id == hw.id
        )
    ]
    for sid in sub_ids:
        background_tasks.add_task(judge_submission, sid, count_submit=False)
    return ok(
        {"homework_id": hw.id, "rejudge_count": len(sub_ids)},
        message="重评任务已提交",
    )


@router.post("/{homework_id}/open-feedback")
def open_feedback(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    hw = _get_owned_homework(db, homework_id, current.user.teacher_no)
    hw.feedback_visible = 1
    db.commit()
    return ok(
        {"homework_id": hw.id, "feedback_visible": 1},
        message="AI 反馈已提前开放",
    )
