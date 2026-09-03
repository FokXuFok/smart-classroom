# -*- coding: utf-8 -*-
"""管理端 / 辅导员端 / 课堂互动 / 通知模块集成测试（TestClient + 真实库）

沙箱策略（模块级）：
- setup：admin 表为空 → 先 upsert 一条 admin（admin/admin123），teardown 删除恢复；
- 记录 classroom_interaction / notification / attendance_record / audit_log 的
  max(id)，teardown 删除 id > max 的自建数据；
- 测试内通过 API 自建自删（T999 教师、pytest- 作业），考勤缺勤行按 id 清理。
"""
import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core.security import hash_password
from app.database import SessionLocal
from app.main import app
from app.models import (
    Admin,
    AttendanceRecord,
    AuditLog,
    ClassroomInteraction,
    Enrollment,
    GradeBook,
    Notification,
    Student,
)
from tests.conftest import login_cookies

client = TestClient(app)

STUDENT = "2024001"
# CS101 实际选课学生（以库为准：2024001/2024002/2451200817）
ENROLLED_CS101 = {"2024001", "2024002", "2024003", "2024004", "2451200817"}


@pytest.fixture(scope="module", autouse=True)
def db_sandbox():
    """admin 账号 upsert + max(id) 基线 + teardown 恢复"""
    db = SessionLocal()
    try:
        created_admin = False
        if db.query(Admin).filter(Admin.admin_no == "admin").first() is None:
            db.add(
                Admin(
                    admin_no="admin",
                    name="系统管理员",
                    password=hash_password("admin123"),
                    status=1,
                )
            )
            db.commit()
            created_admin = True
        maxes = {
            "inter": db.query(func.max(ClassroomInteraction.id)).scalar() or 0,
            "notif": db.query(func.max(Notification.id)).scalar() or 0,
            "att": db.query(func.max(AttendanceRecord.id)).scalar() or 0,
            "audit": db.query(func.max(AuditLog.id)).scalar() or 0,
        }
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        db.query(ClassroomInteraction).filter(
            ClassroomInteraction.id > maxes["inter"]
        ).delete(synchronize_session=False)
        db.query(Notification).filter(
            Notification.id > maxes["notif"]
        ).delete(synchronize_session=False)
        db.query(AttendanceRecord).filter(
            AttendanceRecord.id > maxes["att"]
        ).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.id > maxes["audit"]).delete(
            synchronize_session=False
        )
        if created_admin:
            db.query(Admin).filter(Admin.admin_no == "admin").delete(
                synchronize_session=False
            )
        db.commit()
    finally:
        db.close()


@pytest.fixture(scope="module")
def admin_token():
    return login_cookies("admin", "admin123", "admin")


@pytest.fixture(scope="module")
def teacher_token():
    return login_cookies("T001", "123456", "teacher")


@pytest.fixture(scope="module")
def counselor_token():
    return login_cookies("C001", "123456", "counselor")


@pytest.fixture(scope="module")
def student_token():
    return login_cookies(STUDENT, "123456", "student")


# ---------- 管理端：数据驾驶舱 ----------

def test_admin_overview(admin_token):
    resp = client.get("/api/admin/stat/overview", cookies=admin_token)
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["student_count"] == 5
    assert data["teacher_count"] >= 2
    assert data["course_count"] >= 3
    assert data["class_count"] >= 3
    assert len(data["attendance_trend"]) == 7
    assert all({"date", "count"} <= set(x) for x in data["attendance_trend"])


# ---------- 管理端：人员 CRUD 全流程 ----------

def test_admin_user_crud_loop(admin_token):
    # 新增教师 T999
    resp = client.post(
        "/api/admin/users",
        json={
            "role": "teacher",
            "user_no": "T999",
            "name": "测试教师",
            "department": "pytest系",
            "phone": "13800000099",
        },
        cookies=admin_token,
    )
    assert resp.json()["code"] == 0, resp.json()

    # 编号重复 → 400
    resp = client.post(
        "/api/admin/users",
        json={"role": "teacher", "user_no": "T999", "name": "重复"},
        cookies=admin_token,
    )
    assert resp.json()["code"] == 400

    # 搜索可见，且不泄露 password / face_template
    resp = client.get(
        "/api/admin/users",
        params={"role": "teacher", "keyword": "T999"},
        cookies=admin_token,
    )
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert item["name"] == "测试教师"
    assert item["department"] == "pytest系"
    assert "password" not in item
    assert "face_template" not in item

    # 更新基本信息
    resp = client.put(
        "/api/admin/users/teacher/T999",
        json={"name": "改名的教师", "title": "讲师"},
        cookies=admin_token,
    )
    assert resp.json()["code"] == 0
    resp = client.get(
        "/api/admin/users",
        params={"role": "teacher", "keyword": "T999"},
        cookies=admin_token,
    )
    assert resp.json()["data"]["items"][0]["name"] == "改名的教师"

    # 重置密码 → 默认 123456 可登录
    resp = client.post(
        "/api/admin/users/teacher/T999/reset-password", cookies=admin_token
    )
    assert resp.json()["code"] == 0
    body = TestClient(app).post(
        "/api/auth/login",
        json={"username": "T999", "password": "123456"},
    ).json()
    assert body["code"] == 0, body

    # 禁用 → 登录被拒（1003 账号被禁用）
    resp = client.post(
        "/api/admin/users/teacher/T999/toggle-status", cookies=admin_token
    )
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["status"] == 0
    body = TestClient(app).post(
        "/api/auth/login",
        json={"username": "T999", "password": "123456"},
    ).json()
    assert body["code"] in (403, 1003)

    # 删除 → 列表不再可见
    resp = client.delete(
        "/api/admin/users/teacher/T999", cookies=admin_token
    )
    assert resp.json()["code"] == 0
    resp = client.get(
        "/api/admin/users",
        params={"role": "teacher", "keyword": "T999"},
        cookies=admin_token,
    )
    assert resp.json()["data"]["total"] == 0

    # 管理员不能删除自己
    resp = client.delete(
        "/api/admin/users/admin/admin", cookies=admin_token
    )
    assert resp.json()["code"] == 400


def test_admin_audit_has_records(admin_token):
    resp = client.get(
        "/api/admin/audit",
        params={"action": "user_create", "page": 1, "page_size": 10},
        cookies=admin_token,
    )
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1
    row = next(
        r
        for r in body["data"]["items"]
        if r["target_id"] == "T999" and r["user_role"] == "admin"
    )
    assert row["user_id"] == "admin"
    assert row["action"] == "user_create"


def test_admin_delete_user_precheck(admin_token):
    """删除预检：有关联业务数据必须 400，防 CASCADE 静默级联删除。

    先用临时数据验证（预检缺失时删除会成功并级联清掉课程/选课），
    临时段断言失败则种子数据段不会执行，避免真实数据被破坏。
    """
    # -- 沙箱：临时教师 T998 + 课程 CS998 + 临时学生 S2024998 选课 --
    resp = client.post(
        "/api/admin/users",
        json={"role": "teacher", "user_no": "T998", "name": "预检测试教师"},
        cookies=admin_token,
    )
    assert resp.json()["code"] == 0, resp.json()
    resp = client.post(
        "/api/admin/courses",
        json={"course_id": "CS998", "course_name": "预检测试课程",
              "teacher_id": "T998"},
        cookies=admin_token,
    )
    assert resp.json()["code"] == 0, resp.json()
    resp = client.post(
        "/api/admin/users",
        json={"role": "student", "user_no": "S2024998", "name": "预检测试生",
              "class_id": "CLS001"},
        cookies=admin_token,
    )
    assert resp.json()["code"] == 0, resp.json()
    resp = client.post(
        "/api/admin/enrollments",
        json={"course_id": "CS998", "student_no": "S2024998"},
        cookies=admin_token,
    )
    assert resp.json()["code"] == 0, resp.json()

    try:
        # 教师名下有课程 → 400，且课程/选课完好
        resp = client.delete(
            "/api/admin/users/teacher/T998", cookies=admin_token
        )
        body = resp.json()
        assert body["code"] == 400, "有课程的教师不可删除"
        assert "课程" in body["message"]
        courses = client.get(
            "/api/admin/courses", cookies=admin_token
        ).json()["data"]
        assert any(c["course_id"] == "CS998" for c in courses)

        # 学生有选课 → 400
        resp = client.delete(
            "/api/admin/users/student/S2024998", cookies=admin_token
        )
        body = resp.json()
        assert body["code"] == 400, "有选课的学生不可删除"
        assert "选课" in body["message"]
    finally:
        # 沙箱清理（预检生效时逐层退选/删课/删人；预检缺失时级联已删，接口 404 无害）
        db = SessionLocal()
        try:
            db.query(Enrollment).filter(
                Enrollment.course_id == "CS998"
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
        client.delete("/api/admin/courses/CS998", cookies=admin_token)
        client.delete("/api/admin/users/teacher/T998", cookies=admin_token)
        client.delete(
            "/api/admin/users/student/S2024998", cookies=admin_token
        )

    # -- 种子数据抽查：真实关联数据同样拒绝 --
    resp = client.delete("/api/admin/users/teacher/T001", cookies=admin_token)
    body = resp.json()
    assert body["code"] == 400, "T001 名下有课程，不可删除"
    assert "课程" in body["message"]

    resp = client.delete(
        "/api/admin/users/student/2024001", cookies=admin_token
    )
    body = resp.json()
    assert body["code"] == 400, "2024001 有选课记录，不可删除"
    assert "选课" in body["message"]

    resp = client.delete(
        "/api/admin/users/counselor/C001", cookies=admin_token
    )
    body = resp.json()
    assert body["code"] == 400, "C001 仍管辖班级，不可删除"
    assert "班级" in body["message"]


def test_admin_cannot_disable_self_via_update(admin_token):
    """update_user 直接把本人 status 置 0 → 400（堵 Minor-2）"""
    resp = client.put(
        "/api/admin/users/admin/admin",
        json={"status": 0},
        cookies=admin_token,
    )
    body = resp.json()
    try:
        assert body["code"] == 400, "不能通过编辑接口禁用当前登录管理员"
        assert "不能禁用" in body["message"]
    finally:
        # 兜底恢复：断言失败（预检缺失）时保证 admin 不被留在禁用态
        db = SessionLocal()
        try:
            row = db.query(Admin).filter(Admin.admin_no == "admin").first()
            if row is not None and row.status == 0:
                row.status = 1
                db.commit()
        finally:
            db.close()
    # 当前 token 仍可用
    resp = client.get(
        "/api/admin/users",
        params={"role": "teacher", "page_size": 1},
        cookies=admin_token,
    )
    assert resp.json()["code"] == 0


# ---------- 辅导员端 ----------

def test_counselor_classes(counselor_token):
    resp = client.get("/api/counselor/classes", cookies=counselor_token)
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data, "C001 应至少管辖一个班级"
    codes = {c["class_id"] for c in data}
    assert {"CLS001", "CLS002"} <= codes
    assert all("student_count" in c and c["class_name"] for c in data)


def test_counselor_students(counselor_token):
    resp = client.get(
        "/api/counselor/students",
        params={"class_id": "CLS001"},
        cookies=counselor_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    nos = {s["student_no"] for s in body["data"]}
    assert STUDENT in nos
    assert all("status" in s and "name" in s for s in body["data"])
    # 非管辖班级（C001 不管 CLS003）→ 403
    resp = client.get(
        "/api/counselor/students",
        params={"class_id": "CLS003"},
        cookies=counselor_token,
    )
    assert resp.json()["code"] == 403


def test_counselor_warnings_structure(counselor_token):
    resp = client.get("/api/counselor/warnings", cookies=counselor_token)
    body = resp.json()
    assert body["code"] == 0, body
    for w in body["data"]:
        assert {"student_no", "name", "class_name", "attendance_rate",
                "absent_count", "reasons"} <= set(w)
        assert isinstance(w["reasons"], list) and w["reasons"]


def test_counselor_warning_triggered(counselor_token):
    # 构造预警：给 2024001 插 3 条缺勤（course CS101，session NULL，status 0）
    db = SessionLocal()
    today = datetime.date.today()
    ids = []
    try:
        for _ in range(3):
            rec = AttendanceRecord(
                course_id="CS101",
                student_id=STUDENT,
                attendance_date=today,
                status=0,
                session_id=None,
            )
            db.add(rec)
            db.flush()
            ids.append(rec.id)
        db.commit()
    finally:
        db.close()

    try:
        resp = client.get(
            "/api/counselor/warnings", cookies=counselor_token
        )
        body = resp.json()
        assert body["code"] == 0, body
        target = next(
            (w for w in body["data"] if w["student_no"] == STUDENT), None
        )
        assert target is not None, "3 条缺勤应触发预警"
        assert "缺勤" in "".join(target["reasons"])
        assert target["absent_count"] >= 3
    finally:
        db = SessionLocal()
        try:
            db.query(AttendanceRecord).filter(
                AttendanceRecord.id.in_(ids)
            ).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_counselor_student_profile(counselor_token):
    resp = client.get(
        f"/api/counselor/student/{STUDENT}/profile",
        cookies=counselor_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    # 三段式档案：基本信息+班级 / 出勤 / 成绩 / 互动
    assert data["student"]["student_no"] == STUDENT
    assert data["student"]["class_id"] == "CLS001"
    assert data["student"]["class_name"]
    assert "attendance_rate" in data["attendance"]
    assert "recent" in data["attendance"]
    assert "status_count" in data["attendance"]
    assert isinstance(data["grades"], list)
    assert isinstance(data["interactions"], list)
    for g in data["grades"]:
        assert "homework_title" in g and "score" in g and "judge_time" in g


def test_counselor_stat(counselor_token):
    resp = client.get("/api/counselor/stat", cookies=counselor_token)
    body = resp.json()
    assert body["code"] == 0, body
    data = body["data"]
    assert data["class_count"] >= 2
    assert data["student_total"] >= 4
    assert "avg_attendance_rate" in data
    assert data["warning_count"] >= 0


def test_counselor_warning_homework_only(counselor_token):
    """规则解耦：无任何签到记录 + 2 次作业低于班级均分 20 分 → 仍触发作业预警。

    造数：CLS001 新生 2024999（无签到），GradeBook 两次作业 40 分；
    同作业给 2024001 造 90 分 → 班级均分 65，差 25 > 20。
    清理：按数值 id 删 grade_book（规避 collation 差异），按主键删学生。
    """
    sno = "2024999"
    hw_ids = [99000001, 99000002]
    gb_ids = []
    now = datetime.datetime(2026, 8, 14, 12, 0, 0)
    db = SessionLocal()
    try:
        db.add(Student(student_no=sno, name="作业预警测试生", class_id="CLS001", status=1))
        for hw in hw_ids:
            db.add(GradeBook(course_id="CS101", homework_id=hw, student_id=sno,
                             score=40, judge_time=now))
            db.add(GradeBook(course_id="CS101", homework_id=hw, student_id=STUDENT,
                             score=90, judge_time=now))
        db.commit()
        gb_ids = [
            r.id
            for r in db.query(GradeBook.id)
            .filter(GradeBook.homework_id.in_(hw_ids))
            .all()
        ]
    finally:
        db.close()

    try:
        resp = client.get("/api/counselor/warnings", cookies=counselor_token)
        body = resp.json()
        assert body["code"] == 0, body
        target = next(
            (w for w in body["data"] if w["student_no"] == sno), None
        )
        assert target is not None, "无签到但有低分作业的学生应触发作业预警"
        assert len(target["reasons"]) == 1, "仅应含作业预警，不应有出勤类预警"
        assert "作业" in target["reasons"][0]
        assert target["attendance_rate"] is None
        assert target["absent_count"] == 0
    finally:
        db = SessionLocal()
        try:
            db.query(GradeBook).filter(GradeBook.id.in_(gb_ids)).delete(
                synchronize_session=False
            )
            db.query(Student).filter(Student.student_no == sno).delete(
                synchronize_session=False
            )
            db.commit()
        finally:
            db.close()


# ---------- 课堂互动 ----------

def test_interaction_flow(teacher_token, student_token):
    # 教师记录提问互动
    resp = client.post(
        "/api/interaction/",
        json={
            "course_id": "CS101",
            "interaction_type": "question",
            "student_id": STUDENT,
            "content": "pytest 课堂提问",
        },
        cookies=teacher_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    rec_id = body["data"]["id"]
    assert body["data"]["teacher_id"] == "T001"
    assert body["data"]["lesson_date"]

    # 参数校验：question 缺 student_id → 400；rating 分数越界 → 400
    resp = client.post(
        "/api/interaction/",
        json={"course_id": "CS101", "interaction_type": "question",
              "content": "无学生"},
        cookies=teacher_token,
    )
    assert resp.json()["code"] == 400
    resp = client.post(
        "/api/interaction/",
        json={"course_id": "CS101", "interaction_type": "rating",
              "student_id": STUDENT, "score": 6},
        cookies=teacher_token,
    )
    assert resp.json()["code"] == 400

    # 教师互动历史可见
    resp = client.get(
        "/api/interaction/list",
        params={"course_id": "CS101", "student_id": STUDENT},
        cookies=teacher_token,
    )
    items = resp.json()["data"]
    assert any(x["id"] == rec_id for x in items)

    # 随机点名：返回选课学生之一
    resp = client.get(
        "/api/interaction/random-pick/CS101", cookies=teacher_token
    )
    body = resp.json()
    assert body["code"] == 0, body
    assert body["data"]["student_no"] in ENROLLED_CS101
    assert body["data"]["name"]

    # 统计：question 至少 1 条（本次），total 含 question+random_pick
    resp = client.get(
        "/api/interaction/stats/CS101", cookies=teacher_token
    )
    data = resp.json()["data"]
    assert data["by_type"].get("question", 0) >= 1
    assert data["total"] >= 2
    assert data["top_students"]

    # 学生本人互动历史可见
    resp = client.get(
        "/api/interaction/my",
        params={"course_id": "CS101"},
        cookies=student_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    assert any(x["id"] == rec_id for x in body["data"])


# ---------- 通知 ----------

def test_notification_flow(teacher_token, student_token):
    # 教师创建作业 → 选课学生收到 homework_publish 通知
    resp = client.post(
        "/api/homework/",
        json={
            "course_id": "CS101",
            "title": "pytest-通知钩子作业",
            "description": "通知测试",
            "programming_language": "python",
            "max_score": 100,
            "test_cases": [],
        },
        cookies=teacher_token,
    )
    assert resp.json()["code"] == 0, resp.json()
    hw_id = resp.json()["data"]["homework_id"]

    try:
        resp = client.get(
            "/api/notification/list", params={"limit": 50},
            cookies=student_token,
        )
        body = resp.json()
        assert body["code"] == 0, body
        target = next(
            (
                n
                for n in body["data"]["items"]
                if n["notif_type"] == "homework_publish"
                and n["related_id"] == hw_id
            ),
            None,
        )
        assert target is not None, "应收到作业发布通知"
        assert target["is_read"] == 0
        assert body["data"]["unread_count"] >= 1

        # read-all → 未读清零
        resp = client.post(
            "/api/notification/read-all", cookies=student_token
        )
        assert resp.json()["code"] == 0
        resp = client.get(
            "/api/notification/list", cookies=student_token
        )
        assert resp.json()["data"]["unread_count"] == 0
    finally:
        client.delete(f"/api/homework/{hw_id}", cookies=teacher_token)


# ---------- 越权抽查 ----------

def test_authz(student_token, counselor_token, teacher_token):
    # 学生调管理端接口 → 401（学生角色未登录，require_roles 精确认证）
    resp = client.get(
        "/api/admin/users",
        params={"role": "teacher"},
        cookies=student_token,
    )
    assert resp.json()["code"] == 401

    # 辅导员调教师互动接口（CS103 属 T002）→ 401（辅导员角色无教师身份）
    resp = client.post(
        "/api/interaction/",
        json={
            "course_id": "CS103",
            "interaction_type": "question",
            "student_id": "2024003",
            "content": "越权",
        },
        cookies=counselor_token,
    )
    assert resp.json()["code"] == 401

    # T001 操作 T002 的课程（CS103）→ 403（同角色横向越权）
    resp = client.get(
        "/api/interaction/random-pick/CS103", cookies=teacher_token
    )
    assert resp.json()["code"] == 403

    # 学生查辅导员预警 → 401（学生角色未登录辅导员身份）
    resp = client.get(
        "/api/counselor/warnings", cookies=student_token
    )
    assert resp.json()["code"] == 401
