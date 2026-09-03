# -*- coding: utf-8 -*-
"""越权回归测试（审查修复后补充）：教师横向越权防护"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import forge_cookies, login_cookies

client = TestClient(app)


@pytest.fixture(scope="module")
def t001_token():
    return login_cookies("T001", "123456", "teacher")


@pytest.fixture()
def t002_token():
    # T002 不授课 CS101（属 T001）
    return forge_cookies("T002", "teacher", "李沛")


def test_dashboard_denied_for_other_teacher(t001_token, t002_token):
    # T001 发起 CS101 会话
    resp = client.post(
        "/api/teacher/checkin/start",
        json={"course_id": "CS101"},
        cookies=t001_token,
    )
    assert resp.json()["code"] == 0
    sid = resp.json()["data"]["id"]

    # T002 查看该会话看板 → 403
    resp = client.get(f"/api/teacher/checkin/dashboard/{sid}", cookies=t002_token)
    assert resp.json()["code"] == 403

    # T001 本人可查看 → 0
    resp = client.get(f"/api/teacher/checkin/dashboard/{sid}", cookies=t001_token)
    assert resp.json()["code"] == 0

    # 清理：结束会话并删除（避免污染库）
    client.post(f"/api/teacher/checkin/{sid}/end", cookies=t001_token)


def test_review_denied_for_other_teacher(t001_token, t002_token):
    # T001 发起并结束会话 → 产生一条缺勤记录（2024001 选了 CS101）
    resp = client.post(
        "/api/teacher/checkin/start",
        json={"course_id": "CS101", "duration_minutes": 1},
        cookies=t001_token,
    )
    sid = resp.json()["data"]["id"]
    resp = client.post(f"/api/teacher/checkin/{sid}/end", cookies=t001_token)
    assert resp.json()["code"] == 0
    # 从库里取 2024001 在该会话的缺勤记录
    from app.database import SessionLocal
    from app.models import AttendanceRecord, CheckinSession

    db = SessionLocal()
    rec = (
        db.query(AttendanceRecord)
        .filter(
            AttendanceRecord.session_id == sid,
            AttendanceRecord.student_id == "2024001",
        )
        .first()
    )
    db.close()
    if rec is None:
        pytest.skip("未产生缺勤记录")
    record_id = rec.id

    # T002 审核该记录 → 403
    resp = client.post(
        f"/api/teacher/checkin/attendance/{record_id}/review",
        json={"action": "approve"},
        cookies=t002_token,
    )
    assert resp.json()["code"] == 403

    # 清理测试产生的考勤记录与会话
    db = SessionLocal()
    db.query(AttendanceRecord).filter(AttendanceRecord.session_id == sid).delete(
        synchronize_session=False
    )
    db.query(CheckinSession).filter(CheckinSession.id == sid).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


def test_checkin_sessions_history(t001_token):
    """教师会话历史接口：发起→列表含该会话（进行中）→结束→列表 status=0"""
    # T001 发起 CS101 会话
    resp = client.post(
        "/api/teacher/checkin/start",
        json={"course_id": "CS101", "duration_minutes": 1},
        cookies=t001_token,
    )
    assert resp.json()["code"] == 0
    sid = resp.json()["data"]["id"]

    try:
        # 列表应含该会话，且为进行中
        resp = client.get("/api/teacher/checkin/sessions", cookies=t001_token)
        assert resp.json()["code"] == 0
        rows = resp.json()["data"]
        row = next((r for r in rows if r["id"] == sid), None)
        assert row is not None, "历史列表应包含刚发起的会话"
        assert row["status"] == 1
        assert row["course_id"] == "CS101"
        assert row["course_name"], "应联表返回课程名"
        assert "signed_count" in row

        # course_id 过滤：CS102 下不应出现该 CS101 会话
        resp = client.get(
            "/api/teacher/checkin/sessions",
            params={"course_id": "CS102"},
            cookies=t001_token,
        )
        assert resp.json()["code"] == 0
        assert all(r["id"] != sid for r in resp.json()["data"])

        # 越权：学生 cookie 访问 → 401（学生角色未登录教师身份）
        st_cookies = login_cookies("2024001", "123456", "student")
        resp = client.get("/api/teacher/checkin/sessions", cookies=st_cookies)
        assert resp.json()["code"] == 401

        # 结束后列表 status=0
        resp = client.post(f"/api/teacher/checkin/{sid}/end", cookies=t001_token)
        assert resp.json()["code"] == 0
        resp = client.get("/api/teacher/checkin/sessions", cookies=t001_token)
        row = next(
            (r for r in resp.json()["data"] if r["id"] == sid), None
        )
        assert row is not None and row["status"] == 0
    finally:
        # 清理：结束产生的考勤记录与会话本身
        from app.database import SessionLocal
        from app.models import AttendanceRecord, CheckinSession

        db = SessionLocal()
        db.query(AttendanceRecord).filter(AttendanceRecord.session_id == sid).delete(
            synchronize_session=False
        )
        db.query(CheckinSession).filter(CheckinSession.id == sid).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_cross_role_endpoint_denied():
    """跨角色隔离：不同角色 cookie 调对方端点一律 401（该角色未登录）

    多角色并存下，学生 cookie（sc_token_student）调教师接口时后端只认
    sc_token_teacher，缺失即 401 → 前端跳登录页，不会"串号"到教师身份。
    """
    st_token = login_cookies("2024001", "123456", "student")
    # 学生 cookie 调教师专属接口 → 401
    resp = client.get("/api/teacher/checkin/sessions", cookies=st_token)
    assert resp.json()["code"] == 401
    resp = client.get("/api/teacher/courses", cookies=st_token)
    assert resp.json()["code"] == 401

    t_token = login_cookies("T001", "123456", "teacher")
    # 教师 cookie 调学生专属接口 → 401
    resp = client.get("/api/student/courses", cookies=t_token)
    assert resp.json()["code"] == 401
    resp = client.get("/api/student/checkin/active", cookies=t_token)
    assert resp.json()["code"] == 401

    # 身份归属：各自角色 cookie 调 /me 都返回自身身份，互不干扰
    resp = client.get("/api/auth/me", cookies=t_token)
    body = resp.json()["data"]
    assert body["role"] == "teacher"
    assert body["user_id"] == "T001"
    resp = client.get("/api/auth/me", cookies=st_token)
    body = resp.json()["data"]
    assert body["role"] == "student"
    assert body["user_id"] == "2024001"
