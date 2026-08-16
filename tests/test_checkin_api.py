# -*- coding: utf-8 -*-
"""签到模块 API 集成测试（TestClient + 真实库，参照 test_security.py 样板）

清理策略：记录插入前 checkin_session / attendance_record 的 max(id)，
测试后 delete id > max；2024001 仅临时写假模板，teardown 恢复原值。
"""
import datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core import face_engine
from app.core.geofence import DEFAULT_COORD, haversine_m
from app.core.security import create_token
from app.database import SessionLocal
from app.main import app
from app.models import AttendanceRecord, CheckinSession, Student

client = TestClient(app)

STUDENT = "2024001"
IMG = "!!!not-base64!!!"  # 非法 base64：自拍保存被跳过，避免测试产生磁盘垃圾
NEAR_COORD = {"lat": DEFAULT_COORD[0], "lng": DEFAULT_COORD[1]}
FAR_COORD = {"lat": 25.30, "lng": 110.35}  # 距默认坐标约 3.6 公里


class FakeEngine:
    """假人脸引擎：相似度可控，避免加载真实 InsightFace 模型"""

    def __init__(self, sim=0.9):
        self.sim = sim

    def embed_b64_best(self, image_b64):
        return np.full(512, 0.01, dtype=np.float32), object()

    def compare_with_template(self, template_bytes, embedding):
        return self.sim

    def embedding_to_bytes(self, embedding):
        return np.asarray(embedding, dtype=np.float32).tobytes()

    def liveness_two_frames(self, b64_1, b64_2):
        return {"passed": True, "reason": "fake-liveness"}


def use_fake_engine(monkeypatch, sim=0.9):
    monkeypatch.setattr(face_engine, "get_engine", lambda: FakeEngine(sim))


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def teacher_token():
    resp = client.post(
        "/api/auth/login",
        json={"username": "T001", "password": "123456", "role": "teacher"},
    )
    assert resp.json()["code"] == 0
    return resp.json()["data"]["token"]


@pytest.fixture(scope="module")
def student_token():
    resp = client.post(
        "/api/auth/login",
        json={"username": STUDENT, "password": "123456", "role": "student"},
    )
    assert resp.json()["code"] == 0
    return resp.json()["data"]["token"]


@pytest.fixture(autouse=True)
def db_sandbox():
    """只清理本文件测试产生的签到会话与考勤记录"""
    db = SessionLocal()
    max_session = db.query(func.max(CheckinSession.id)).scalar() or 0
    max_record = db.query(func.max(AttendanceRecord.id)).scalar() or 0
    db.close()
    yield
    db = SessionLocal()
    # 先删子表（attendance_record）再删父表（checkin_session），避免外键约束
    db.query(AttendanceRecord).filter(AttendanceRecord.id > max_record).delete(
        synchronize_session=False
    )
    db.query(CheckinSession).filter(CheckinSession.id > max_session).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


@pytest.fixture()
def temp_template():
    """给 2024001 临时写 512 维随机假模板，teardown 恢复原值"""
    db = SessionLocal()
    st = db.get(Student, STUDENT)
    old = (st.face_template, st.face_regen_allowed)
    st.face_template = np.random.rand(512).astype(np.float32).tobytes()
    st.face_regen_allowed = 0
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    st = db.get(Student, STUDENT)
    st.face_template, st.face_regen_allowed = old
    db.commit()
    db.close()


@pytest.fixture()
def reset_2024002_face():
    """t10 给 2024002 注册人脸后恢复原值"""
    db = SessionLocal()
    st = db.get(Student, "2024002")
    old = (st.face_template, st.face_image_url, st.face_regen_allowed)
    db.close()
    yield
    db = SessionLocal()
    st = db.get(Student, "2024002")
    st.face_template, st.face_image_url, st.face_regen_allowed = old
    db.commit()
    db.close()


def start_session(teacher_token, course_id="CS101", **extra):
    payload = {"course_id": course_id}
    payload.update(extra)
    resp = client.post(
        "/api/teacher/checkin/start", json=payload, headers=auth(teacher_token)
    )
    assert resp.json()["code"] == 0
    return resp.json()["data"]


def submit(token, session_id, coords=NEAR_COORD, **extra):
    payload = {"session_id": session_id, "image_b64": IMG, **coords, **extra}
    return client.post(
        "/api/student/checkin/submit", json=payload, headers=auth(token)
    )


# ---------- t1 发起签到：未传经纬度 → 默认坐标 used_default=True ----------

def test_t1_start_checkin_used_default(teacher_token):
    data = start_session(teacher_token)
    assert data["used_default"] is True
    # MySQL FLOAT 为单精度，用近似比较
    assert data["teacher_lat"] == pytest.approx(DEFAULT_COORD[0], abs=1e-3)
    assert data["teacher_lng"] == pytest.approx(DEFAULT_COORD[1], abs=1e-3)
    assert data["status"] == 1
    assert data["deadline"] is not None


# ---------- t2 非本人课程发起 → 403 ----------

def test_t2_start_other_teacher_course():
    token = create_token("T002", "teacher", "测试教师")
    resp = client.post(
        "/api/teacher/checkin/start",
        json={"course_id": "CS101"},  # 属 T001
        headers=auth(token),
    )
    assert resp.json()["code"] == 403


# ---------- t3 未注册人脸提交 → 2001 ----------

def test_t3_submit_without_face_template(teacher_token, student_token):
    sid = start_session(teacher_token)["id"]
    resp = submit(student_token, sid)
    assert resp.json()["code"] == 2001


# ---------- t4 距离超范围 → 2003（message 含实际距离） ----------

def test_t4_submit_out_of_range(teacher_token, student_token, temp_template):
    sid = start_session(teacher_token)["id"]
    resp = submit(student_token, sid, coords=FAR_COORD)
    body = resp.json()
    assert body["code"] == 2003
    # 用库中实际存储的会话坐标计算期望距离，与 API 口径一致
    db = SessionLocal()
    s = db.get(CheckinSession, sid)
    expect_m = round(
        haversine_m(s.teacher_lat, s.teacher_lng, FAR_COORD["lat"], FAR_COORD["lng"])
    )
    db.close()
    assert str(expect_m) in body["message"]


# ---------- t5 相似度不足 → 2002 且产生待复核记录 ----------

def test_t5_low_similarity_to_review(teacher_token, student_token, temp_template, monkeypatch):
    use_fake_engine(monkeypatch, sim=0.2)
    sid = start_session(teacher_token)["id"]
    resp = submit(student_token, sid)
    assert resp.json()["code"] == 2002

    db = SessionLocal()
    rec = (
        db.query(AttendanceRecord)
        .filter_by(session_id=sid, student_id=STUDENT)
        .first()
    )
    db.close()
    assert rec is not None
    assert rec.review_status == 1
    assert rec.status == 0


# ---------- t6 相似度 0.9 + 范围内 → 成功；再次提交 → 2005 ----------

def test_t6_submit_success_and_duplicate(teacher_token, student_token, temp_template, monkeypatch):
    use_fake_engine(monkeypatch, sim=0.9)
    sid = start_session(teacher_token)["id"]

    resp = submit(student_token, sid)
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["status"] == 1
    assert body["data"]["similarity"] == pytest.approx(0.9, abs=1e-6)
    assert body["data"]["fingerprint"]["enabled"] is False  # 预留接口不阻断
    assert body["data"]["liveness"]["passed"] is True       # 未采集第二帧默认通过

    resp2 = submit(student_token, sid)
    assert resp2.json()["code"] == 2005


# ---------- t7 迟到判定：create_time 改为 15 分钟前 → status=2 ----------

def test_t7_late_judgement(teacher_token, student_token, temp_template, monkeypatch):
    use_fake_engine(monkeypatch, sim=0.9)
    # 时长给足 30 分钟，保证改 create_time 后会话仍在进行中
    sid = start_session(teacher_token, duration_minutes=30)["id"]
    db = SessionLocal()
    s = db.get(CheckinSession, sid)
    s.create_time = datetime.datetime.now() - datetime.timedelta(minutes=15)
    db.commit()
    db.close()

    resp = submit(student_token, sid)
    assert resp.json()["data"]["status"] == 2


# ---------- t8 教师看板 + 结束会话补缺勤 ----------

def test_t8_dashboard_and_end(teacher_token, student_token, temp_template, monkeypatch):
    use_fake_engine(monkeypatch, sim=0.9)
    sid = start_session(teacher_token)["id"]
    assert submit(student_token, sid).json()["code"] == 0

    resp = client.get(
        f"/api/teacher/checkin/dashboard/{sid}", headers=auth(teacher_token)
    )
    assert resp.json()["code"] == 0
    students = resp.json()["data"]["students"]
    me = next(s for s in students if s["student_no"] == STUDENT)
    assert me["status"] == "正常"
    other = next(s for s in students if s["student_no"] == "2024002")
    assert other["status"] == "未签到"

    resp = client.post(f"/api/teacher/checkin/{sid}/end", headers=auth(teacher_token))
    data = resp.json()["data"]
    assert data["absent_created"] >= 1

    db = SessionLocal()
    absent = (
        db.query(AttendanceRecord).filter_by(session_id=sid, status=0).all()
    )
    db.close()
    assert {a.student_id for a in absent} >= {"2024002", "2451200817"}


# ---------- t9 补签审核 approve：缺勤 0 → 正常 1 ----------

def test_t9_review_approve(teacher_token):
    sid = start_session(teacher_token)["id"]
    client.post(f"/api/teacher/checkin/{sid}/end", headers=auth(teacher_token))

    db = SessionLocal()
    rec = (
        db.query(AttendanceRecord)
        .filter_by(session_id=sid, student_id=STUDENT)
        .first()
    )
    db.close()
    assert rec is not None and rec.status == 0

    resp = client.post(
        f"/api/teacher/checkin/attendance/{rec.id}/review",
        json={"action": "approve", "remark": "情况属实，同意补签"},
        headers=auth(teacher_token),
    )
    assert resp.json()["code"] == 0

    db = SessionLocal()
    rec2 = db.get(AttendanceRecord, rec.id)
    db.close()
    assert rec2.status == 1
    assert rec2.check_in_type == 2
    assert rec2.review_status == 2
    assert rec2.review_remark == "情况属实，同意补签"


# ---------- t10 人脸注册：成功 + 已有模板未授权 → 403 ----------

def test_t10_face_register(monkeypatch, reset_2024002_face):
    use_fake_engine(monkeypatch, sim=0.9)
    tok = create_token("2024002", "student", "李四")

    resp = client.post(
        "/api/student/face/register",
        json={"image_b64": IMG},
        headers=auth(tok),
    )
    assert resp.json()["code"] == 0
    db = SessionLocal()
    st = db.get(Student, "2024002")
    tpl_ok = st.face_template is not None and st.face_regen_allowed == 0
    db.close()
    assert tpl_ok

    # 已有模板且未获教师授权 → 403
    resp2 = client.post(
        "/api/student/face/register",
        json={"image_b64": IMG},
        headers=auth(tok),
    )
    assert resp2.json()["code"] == 403


def test_t10b_face_register_unauthorized_existing(monkeypatch, temp_template, student_token):
    """2024001 已有模板（临时）且未授权 → 403"""
    use_fake_engine(monkeypatch, sim=0.9)
    resp = client.post(
        "/api/student/face/register",
        json={"image_b64": IMG},
        headers=auth(student_token),
    )
    assert resp.json()["code"] == 403
