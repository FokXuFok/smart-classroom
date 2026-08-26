# -*- coding: utf-8 -*-
"""后台管理 API：数据驾驶舱、人员/课程/班级/选课/课表管理、审计日志（全部写操作落 audit_log）"""
import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, get_db, require_roles
from app.core.exception import BizError, ok
from app.core.security import hash_password
from app.models import (
    AcademicAlert,
    Admin,
    AttendanceRecord,
    AuditLog,
    CheckinSession,
    ClassInfo,
    ClassroomInteraction,
    Course,
    Counselor,
    CounselorClass,
    Enrollment,
    Homework,
    Schedule,
    Student,
    SubmissionRecord,
    Teacher,
)
from app.schemas.common import (
    ClassCreateReq,
    ClassUpdateReq,
    CourseCreateReq,
    CourseUpdateReq,
    EnrollmentCreateReq,
    ScheduleCreateReq,
    UserCreateReq,
    UserUpdateReq,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# role → (ORM 类, 主键字段)
ROLE_MODEL = {
    "student": (Student, "student_no"),
    "teacher": (Teacher, "teacher_no"),
    "counselor": (Counselor, "counselor_no"),
    "admin": (Admin, "admin_no"),
}

DEFAULT_PASSWORD = "123456"


# ---------- 公共 helper ----------

def _audit(db, admin_no: str, action: str, target_type=None, target_id=None, detail=None):
    """写审计日志（独立提交）"""
    db.add(
        AuditLog(
            action=action,
            user_id=admin_no,
            user_role="admin",
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail,
        )
    )
    db.commit()


def _get_user(db, role: str, user_id: str):
    if role not in ROLE_MODEL:
        raise BizError(400, "不支持的角色类型")
    model, pk = ROLE_MODEL[role]
    user = db.query(model).filter(getattr(model, pk) == user_id).first()
    if user is None:
        raise BizError(404, "人员不存在")
    return user


def _user_dict(user, role: str, class_name=None) -> dict:
    """人员响应（绝不返回 password / face_template）"""
    _, pk = ROLE_MODEL[role]
    d = {"role": role, "user_id": getattr(user, pk)}
    for f in ("name", "gender", "phone", "email", "status", "create_time"):
        if hasattr(user, f):
            d[f] = getattr(user, f)
    if role == "student":
        d["class_id"] = user.class_id
        d["class_name"] = class_name
    if role in ("teacher", "counselor") and hasattr(user, "department"):
        d["department"] = user.department
    if role == "teacher":
        d["title"] = user.title
    return d


# ---------- 数据驾驶舱 ----------

@router.get("/stat/overview")
def overview(
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=6)
    trend_rows = (
        db.query(AttendanceRecord.attendance_date, func.count(AttendanceRecord.id))
        .filter(AttendanceRecord.attendance_date >= start)
        .group_by(AttendanceRecord.attendance_date)
        .all()
    )
    trend_map = {d: c for d, c in trend_rows}
    trend = [
        {"date": (start + datetime.timedelta(days=i)).isoformat(),
         "count": trend_map.get(start + datetime.timedelta(days=i), 0)}
        for i in range(7)
    ]
    return ok(
        {
            "student_count": db.query(func.count(Student.student_no)).scalar(),
            "teacher_count": db.query(func.count(Teacher.teacher_no)).scalar(),
            "counselor_count": db.query(func.count(Counselor.counselor_no)).scalar(),
            "admin_count": db.query(func.count(Admin.admin_no)).scalar(),
            "course_count": db.query(func.count(Course.course_code)).scalar(),
            "class_count": db.query(func.count(ClassInfo.class_code)).scalar(),
            "attendance_count": db.query(func.count(AttendanceRecord.id)).scalar(),
            "homework_count": db.query(func.count(Homework.id)).scalar(),
            "submission_count": db.query(func.count(SubmissionRecord.id)).scalar(),
            "attendance_trend": trend,
        }
    )


# ---------- 人员管理 ----------

@router.get("/users")
def list_users(
    role: str,
    keyword: str = "",
    page: int = 1,
    page_size: int = 20,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if role not in ROLE_MODEL:
        raise BizError(400, "不支持的角色类型")
    model, pk = ROLE_MODEL[role]
    q = db.query(model)
    if keyword:
        like = f"%{keyword}%"
        conds = [getattr(model, pk).like(like), model.name.like(like)]
        if hasattr(model, "phone"):
            conds.append(model.phone.like(like))
        q = q.filter(or_(*conds))
    total = q.count()
    page, page_size = max(page, 1), max(min(page_size, 100), 1)
    rows = (
        q.order_by(getattr(model, pk))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    class_names = {}
    if role == "student" and rows:
        codes = {u.class_id for u in rows}
        class_names = dict(
            db.query(ClassInfo.class_code, ClassInfo.class_name)
            .filter(ClassInfo.class_code.in_(codes))
            .all()
        )
    items = [
        _user_dict(
            u, role, class_names.get(u.class_id) if role == "student" else None
        )
        for u in rows
    ]
    return ok({"total": total, "items": items})


@router.post("/users")
def create_user(
    req: UserCreateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if req.role not in ("student", "teacher", "counselor"):
        raise BizError(400, "role 必须为 student/teacher/counselor")
    model, pk = ROLE_MODEL[req.role]
    if db.query(model).filter(getattr(model, pk) == req.user_no).first():
        raise BizError(400, "编号已存在")
    if req.role == "student":
        if not req.class_id:
            raise BizError(400, "学生必须指定班级")
        if db.query(ClassInfo).filter(ClassInfo.class_code == req.class_id).first() is None:
            raise BizError(404, "班级不存在")
        user = Student(
            student_no=req.user_no, name=req.name, class_id=req.class_id,
            gender=req.gender, phone=req.phone, email=req.email,
        )
    elif req.role == "teacher":
        user = Teacher(
            teacher_no=req.user_no, name=req.name, gender=req.gender,
            phone=req.phone, email=req.email,
            department=req.department, title=req.title,
        )
    else:
        user = Counselor(
            counselor_no=req.user_no, name=req.name, gender=req.gender,
            phone=req.phone, email=req.email, department=req.department,
        )
    user.password = hash_password(req.password or DEFAULT_PASSWORD)
    user.status = 1
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizError(400, "编号已存在")
    db.refresh(user)
    _audit(
        db, current.user.admin_no, "user_create", "user", req.user_no,
        f"新增{req.role} {req.user_no} {req.name}",
    )
    class_name = None
    if req.role == "student":
        cls = db.query(ClassInfo).filter(ClassInfo.class_code == req.class_id).first()
        class_name = cls.class_name if cls else None
    return ok(_user_dict(user, req.role, class_name), message="人员已创建")


@router.put("/users/{role}/{user_id}")
def update_user(
    role: str,
    user_id: str,
    req: UserUpdateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    user = _get_user(db, role, user_id)
    if role == "admin" and user_id == current.user.admin_no and req.status == 0:
        raise BizError(400, "不能禁用当前登录管理员")
    for field in ("name", "gender", "phone", "email", "department", "title", "status"):
        value = getattr(req, field)
        if value is not None and hasattr(user, field):
            setattr(user, field, value)
    if req.class_id is not None:
        if role != "student":
            raise BizError(400, "仅学生支持 class_id")
        if db.query(ClassInfo).filter(ClassInfo.class_code == req.class_id).first() is None:
            raise BizError(404, "班级不存在")
        user.class_id = req.class_id
    db.commit()
    _audit(
        db, current.user.admin_no, "user_update", "user", user_id,
        f"更新{role} {user_id} 基本信息",
    )
    return ok(_user_dict(user, role), message="人员信息已更新")


@router.post("/users/{role}/{user_id}/reset-password")
def reset_password(
    role: str,
    user_id: str,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if role == "admin":
        raise BizError(400, "不支持重置管理员密码")
    user = _get_user(db, role, user_id)
    user.password = hash_password(DEFAULT_PASSWORD)
    db.commit()
    _audit(
        db, current.user.admin_no, "reset_password", "user", user_id,
        f"重置{role} {user_id} 密码为默认密码",
    )
    return ok({"user_id": user_id, "role": role}, message=f"密码已重置为 {DEFAULT_PASSWORD}")


@router.post("/users/{role}/{user_id}/toggle-status")
def toggle_status(
    role: str,
    user_id: str,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    user = _get_user(db, role, user_id)
    if role == "admin" and user_id == current.user.admin_no:
        raise BizError(400, "不能禁用当前登录管理员")
    cur = getattr(user, "status", 1)
    if cur == 2:        # 待审批 → 审批通过
        user.status = 1
        action = "审批通过"
    elif cur == 1:      # 正常 → 禁用
        user.status = 0
        action = "禁用"
    else:               # 禁用 → 启用
        user.status = 1
        action = "启用"
    db.commit()
    _audit(
        db, current.user.admin_no, "toggle_status", "user", user_id,
        f"{role} {user_id} {action}",
    )
    return ok({"user_id": user_id, "role": role, "status": user.status}, message="状态已切换")


@router.delete("/users/{role}/{user_id}")
def delete_user(
    role: str,
    user_id: str,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if role == "admin" and user_id == current.user.admin_no:
        raise BizError(400, "不能删除当前登录管理员")
    user = _get_user(db, role, user_id)
    # 删除预检：course.teacher_id / enrollment 等外键为 CASCADE，
    # 直接删会静默级联清掉课程/选课等业务数据，故删除前显式计数拦截
    if role == "teacher":
        course_cnt = (
            db.query(func.count(Course.course_code))
            .filter(Course.teacher_id == user_id)
            .scalar()
        )
        if course_cnt:
            raise BizError(400, "该教师名下存在课程（含选课数据），请先转移或删除课程")
    elif role == "student":
        related = [
            db.query(func.count(Enrollment.id)).filter(Enrollment.student_id == user_id).scalar(),
            db.query(func.count(AttendanceRecord.id)).filter(AttendanceRecord.student_id == user_id).scalar(),
            db.query(func.count(SubmissionRecord.id)).filter(SubmissionRecord.student_id == user_id).scalar(),
            db.query(func.count(AcademicAlert.id)).filter(AcademicAlert.student_id == user_id).scalar(),
        ]
        if any(related):
            raise BizError(400, "该学生存在选课/签到/作业数据，无法删除（可改为禁用）")
    elif role == "counselor":
        class_cnt = (
            db.query(func.count(CounselorClass.class_id))
            .filter(CounselorClass.counselor_id == user_id)
            .scalar()
        )
        if class_cnt:
            raise BizError(400, "该辅导员仍管辖班级")
    try:
        db.delete(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizError(400, "该人员存在关联业务数据（选课/签到/作业等），无法删除")
    _audit(
        db, current.user.admin_no, "user_delete", "user", user_id,
        f"删除{role} {user_id}",
    )
    return ok({"user_id": user_id, "role": role}, message="人员已删除")


# ---------- 课程管理 ----------

@router.get("/courses")
def list_courses(
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    rows = (
        db.query(Course, Teacher.name)
        .outerjoin(Teacher, Teacher.teacher_no == Course.teacher_id)
        .order_by(Course.course_code)
        .all()
    )
    data = []
    for c, tname in rows:
        cnt = (
            db.query(func.count(Enrollment.id))
            .filter(Enrollment.course_id == c.course_code, Enrollment.status == 1)
            .scalar()
        )
        data.append(
            {
                "course_id": c.course_code,
                "course_name": c.course_name,
                "credit": float(c.credit) if c.credit is not None else None,
                "hours": c.hours,
                "semester": c.semester,
                "teacher_id": c.teacher_id,
                "teacher_name": tname,
                "status": c.status,
                "student_count": cnt,
            }
        )
    return ok(data)


@router.post("/courses")
def create_course(
    req: CourseCreateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if db.query(Course).filter(Course.course_code == req.course_id).first():
        raise BizError(400, "课程代码已存在")
    if db.query(Teacher).filter(Teacher.teacher_no == req.teacher_id).first() is None:
        raise BizError(404, "授课教师不存在")
    course = Course(
        course_code=req.course_id,
        course_name=req.course_name,
        credit=req.credit,
        hours=req.hours,
        description=req.description,
        semester=req.semester,
        teacher_id=req.teacher_id,
        status=req.status if req.status is not None else 1,
    )
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizError(400, "课程代码已存在")
    _audit(
        db, current.user.admin_no, "course_create", "course", req.course_id,
        f"新增课程 {req.course_id} {req.course_name}",
    )
    return ok({"course_id": req.course_id}, message="课程已创建")


@router.put("/courses/{course_id}")
def update_course(
    course_id: str,
    req: CourseUpdateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    course = db.query(Course).filter(Course.course_code == course_id).first()
    if course is None:
        raise BizError(404, "课程不存在")
    if req.teacher_id is not None:
        if db.query(Teacher).filter(Teacher.teacher_no == req.teacher_id).first() is None:
            raise BizError(404, "授课教师不存在")
        course.teacher_id = req.teacher_id
    for field in ("course_name", "credit", "hours", "description", "semester", "status"):
        value = getattr(req, field)
        if value is not None:
            setattr(course, field, value)
    db.commit()
    _audit(
        db, current.user.admin_no, "course_update", "course", course_id,
        f"更新课程 {course_id}",
    )
    return ok({"course_id": course_id}, message="课程已更新")


@router.delete("/courses/{course_id}")
def delete_course(
    course_id: str,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    course = db.query(Course).filter(Course.course_code == course_id).first()
    if course is None:
        raise BizError(404, "课程不存在")
    related = [
        ("选课记录", db.query(func.count(Enrollment.id)).filter(Enrollment.course_id == course_id).scalar()),
        ("签到会话", db.query(func.count(CheckinSession.id)).filter(CheckinSession.course_id == course_id).scalar()),
        ("签到记录", db.query(func.count(AttendanceRecord.id)).filter(AttendanceRecord.course_id == course_id).scalar()),
        ("作业", db.query(func.count(Homework.id)).filter(Homework.course_id == course_id).scalar()),
        ("课堂互动", db.query(func.count(ClassroomInteraction.id)).filter(ClassroomInteraction.course_id == course_id).scalar()),
    ]
    conflict = [f"{label}{cnt}条" for label, cnt in related if cnt]
    if conflict:
        raise BizError(400, f"该课程存在关联业务数据（{'、'.join(conflict)}），无法删除")
    try:
        db.delete(course)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizError(400, "该课程存在关联业务数据，无法删除")
    _audit(
        db, current.user.admin_no, "course_delete", "course", course_id,
        f"删除课程 {course_id}",
    )
    return ok({"course_id": course_id}, message="课程已删除")


# ---------- 班级管理（student_count 动态统计） ----------

@router.get("/classes")
def list_classes(
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    rows = db.query(ClassInfo).order_by(ClassInfo.class_code).all()
    data = []
    for c in rows:
        cnt = (
            db.query(func.count(Student.student_no))
            .filter(Student.class_id == c.class_code)
            .scalar()
        )
        data.append(
            {
                "class_id": c.class_code,
                "class_name": c.class_name,
                "grade": c.grade,
                "major": c.major,
                "department": c.department,
                "student_count": cnt,
            }
        )
    return ok(data)


@router.post("/classes")
def create_class(
    req: ClassCreateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if db.query(ClassInfo).filter(ClassInfo.class_code == req.class_id).first():
        raise BizError(400, "班级代码已存在")
    cls = ClassInfo(
        class_code=req.class_id,
        class_name=req.class_name,
        grade=req.grade,
        major=req.major,
        department=req.department,
        student_count=0,
    )
    db.add(cls)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizError(400, "班级代码已存在")
    _audit(
        db, current.user.admin_no, "class_create", "class", req.class_id,
        f"新增班级 {req.class_id} {req.class_name}",
    )
    return ok({"class_id": req.class_id}, message="班级已创建")


@router.put("/classes/{class_id}")
def update_class(
    class_id: str,
    req: ClassUpdateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    cls = db.query(ClassInfo).filter(ClassInfo.class_code == class_id).first()
    if cls is None:
        raise BizError(404, "班级不存在")
    for field in ("class_name", "grade", "major", "department"):
        value = getattr(req, field)
        if value is not None:
            setattr(cls, field, value)
    db.commit()
    _audit(
        db, current.user.admin_no, "class_update", "class", class_id,
        f"更新班级 {class_id}",
    )
    return ok({"class_id": class_id}, message="班级已更新")


# ---------- 选课管理 ----------

@router.get("/enrollments")
def list_enrollments(
    course_id: str = "",
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    q = (
        db.query(Enrollment, Student, Course)
        .outerjoin(Student, Student.student_no == Enrollment.student_id)
        .outerjoin(Course, Course.course_code == Enrollment.course_id)
    )
    if course_id:
        q = q.filter(Enrollment.course_id == course_id)
    rows = q.order_by(Enrollment.id.desc()).all()
    return ok(
        [
            {
                "id": e.id,
                "course_id": e.course_id,
                "course_name": c.course_name if c else None,
                "student_no": e.student_id,
                "student_name": s.name if s else None,
                "status": e.status,
                "create_time": e.create_time,
            }
            for e, s, c in rows
        ]
    )


@router.post("/enrollments")
def create_enrollment(
    req: EnrollmentCreateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if db.query(Course).filter(Course.course_code == req.course_id).first() is None:
        raise BizError(404, "课程不存在")
    if db.query(Student).filter(Student.student_no == req.student_no).first() is None:
        raise BizError(404, "学生不存在")
    existing = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == req.course_id,
            Enrollment.student_id == req.student_no,
        )
        .first()
    )
    if existing:  # 幂等：已存在直接返回 ok
        if existing.status == 0:
            existing.status = 1
            db.commit()
        return ok({"id": existing.id}, message="该学生已选此课程")
    e = Enrollment(course_id=req.course_id, student_id=req.student_no, status=1)
    db.add(e)
    db.commit()
    db.refresh(e)
    _audit(
        db, current.user.admin_no, "enrollment_create", "enrollment", e.id,
        f"学生 {req.student_no} 选课 {req.course_id}",
    )
    return ok({"id": e.id}, message="选课成功")


@router.delete("/enrollments/{enroll_id}")
def delete_enrollment(
    enroll_id: int,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    e = db.query(Enrollment).filter(Enrollment.id == enroll_id).first()
    if e is None:
        raise BizError(404, "选课记录不存在")
    course_id, student_no = e.course_id, e.student_id
    try:
        db.delete(e)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizError(400, "该选课记录存在关联业务数据，无法删除")
    _audit(
        db, current.user.admin_no, "enrollment_delete", "enrollment", enroll_id,
        f"学生 {student_no} 退选 {course_id}",
    )
    return ok({"id": enroll_id}, message="已退选")


# ---------- 审计日志 ----------

@router.get("/audit")
def list_audit(
    page: int = 1,
    page_size: int = 20,
    action: str = "",
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    page, page_size = max(page, 1), max(min(page_size, 100), 1)
    rows = (
        q.order_by(AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ok(
        {
            "total": total,
            "items": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "user_role": r.user_role,
                    "action": r.action,
                    "target_type": r.target_type,
                    "target_id": r.target_id,
                    "detail": r.detail,
                    "create_time": r.create_time,
                }
                for r in rows
            ],
        }
    )


# ---------- 课表管理 ----------

@router.get("/schedules")
def list_schedules(
    class_id: str = "",
    weekday: int = 0,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    q = (
        db.query(Schedule, Course.course_name, ClassInfo.class_name)
        .outerjoin(Course, Course.course_code == Schedule.course_id)
        .outerjoin(ClassInfo, ClassInfo.class_code == Schedule.class_id)
    )
    if class_id:
        q = q.filter(Schedule.class_id == class_id)
    if weekday:
        q = q.filter(Schedule.weekday == weekday)
    rows = q.order_by(Schedule.weekday, Schedule.start_time).all()
    return ok(
        [
            {
                "id": s.id,
                "course_id": s.course_id,
                "course_name": cname,
                "class_id": s.class_id,
                "class_name": clsname,
                "weekday": s.weekday,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "weeks": s.weeks,
                "classroom": s.classroom,
            }
            for s, cname, clsname in rows
        ]
    )


@router.post("/schedules")
def create_schedule(
    req: ScheduleCreateReq,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    if db.query(Course).filter(Course.course_code == req.course_id).first() is None:
        raise BizError(404, "课程不存在")
    if db.query(ClassInfo).filter(ClassInfo.class_code == req.class_id).first() is None:
        raise BizError(404, "班级不存在")
    if not 1 <= req.weekday <= 7:
        raise BizError(400, "weekday 必须为 1-7")
    if req.end_time <= req.start_time:
        raise BizError(400, "结束时间必须晚于开始时间")
    s = Schedule(
        course_id=req.course_id,
        class_id=req.class_id,
        weekday=req.weekday,
        start_time=req.start_time,
        end_time=req.end_time,
        weeks=req.weeks or "1-16",
        classroom=req.classroom,
    )
    db.add(s)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise BizError(400, "该班级此时间段已排课")
    db.refresh(s)
    _audit(
        db, current.user.admin_no, "schedule_create", "schedule", s.id,
        f"{req.class_id} 周一至周日第{req.weekday}天 {req.start_time}-{req.end_time} 排课 {req.course_id}",
    )
    return ok({"id": s.id}, message="排课成功")


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    current: CurrentUser = Depends(require_roles("admin")),
    db=Depends(get_db),
):
    s = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if s is None:
        raise BizError(404, "课表记录不存在")
    db.delete(s)
    db.commit()
    _audit(
        db, current.user.admin_no, "schedule_delete", "schedule", schedule_id,
        f"删除课表 {schedule_id}",
    )
    return ok({"id": schedule_id}, message="课表已删除")
