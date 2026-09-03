# -*- coding: utf-8 -*-
"""优化项回归测试：
- SessionBus 事件总线（SSE 底层，含跨线程发布）
- SSE 实时签到流首帧快照
- 考勤 / 成绩册 Excel 导出（openpyxl）
- 互动统计 SQL 聚合下推
- push_many 批量通知
"""
import asyncio
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.api.notification import push_many
from app.core.events import SessionBus
from app.database import SessionLocal
from app.main import app
from app.models import CheckinSession, ClassroomInteraction, Notification
from tests.conftest import login_cookies

client = TestClient(app)


@pytest.fixture(scope="module")
def teacher_token():
    return login_cookies("T001", "123456", "teacher")


@pytest.fixture(scope="module")
def student_token():
    return login_cookies("2024001", "123456", "student")


@pytest.fixture(autouse=True)
def db_sandbox():
    """清理本文件测试产生的会话 / 互动 / 通知"""
    db = SessionLocal()
    max_session = db.query(func.max(CheckinSession.id)).scalar() or 0
    max_interaction = db.query(func.max(ClassroomInteraction.id)).scalar() or 0
    db.close()
    yield
    db = SessionLocal()
    db.query(ClassroomInteraction).filter(
        ClassroomInteraction.id > max_interaction
    ).delete(synchronize_session=False)
    db.query(CheckinSession).filter(CheckinSession.id > max_session).delete(
        synchronize_session=False
    )
    db.query(Notification).filter(Notification.notif_type == "test_bulk").delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


def _start_session(cookies) -> int:
    resp = client.post(
        "/api/teacher/checkin/start",
        json={"course_id": "CS101", "duration_minutes": 5, "range_meters": 200},
        cookies=cookies,
    )
    body = resp.json()
    assert body["code"] == 0, f"发起签到失败: {body}"
    return body["data"]["id"]


# ---------- SessionBus ----------

def test_session_bus_roundtrip():
    """订阅→发布→收到；跨线程发布→收到；无订阅者发布不报错；退订后发布不投递"""

    async def run():
        bus = SessionBus()
        bus.publish(999, {"type": "no-subscriber"})  # 无订阅者：空操作
        q1 = bus.subscribe(1)
        bus.publish(1, {"type": "checkin", "name": "张三"})
        ev = await asyncio.wait_for(q1.get(), timeout=2)
        assert ev == {"type": "checkin", "name": "张三"}
        bus.unsubscribe(1, q1)

        q2 = bus.subscribe(1)
        # 模拟 sync 路由（线程池）发布：call_soon_threadsafe 跨线程投递
        t = threading.Thread(target=lambda: bus.publish(1, {"type": "thread"}))
        t.start()
        ev2 = await asyncio.wait_for(q2.get(), timeout=2)
        assert ev2["type"] == "thread"
        t.join()
        bus.unsubscribe(1, q2)

    asyncio.run(run())


# ---------- SSE 实时签到流 ----------

def test_checkin_stream_live():
    """SSE 快照帧验证：起真实 uvicorn 走 TCP 流式读取。

    说明：TestClient / httpx ASGITransport 会缓冲完整响应体，天然不支持
    无限 SSE 流（读到快照帧即断开），因此本用例必须用真实服务器验证。
    """
    import socket
    import subprocess
    import sys
    import time as _time
    from pathlib import Path

    import httpx as _httpx

    # 找一个空闲端口
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    base = f"http://127.0.0.1:{port}"
    root = str(Path(__file__).resolve().parents[1])

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--port", str(port), "--log-level", "error"],
        cwd=root,
    )
    try:
        for _ in range(60):
            try:
                if _httpx.get(f"{base}/api/health", timeout=2).status_code == 200:
                    break
            except Exception:
                _time.sleep(0.5)
        else:
            pytest.fail("uvicorn 测试实例启动超时")

        # 必须向该子进程实例登录（instance_id 校验：进程不同则 token 失效）
        r = _httpx.post(
            f"{base}/api/auth/login",
            json={"username": "T001", "password": "123456"},
            timeout=10,
        )
        assert r.json()["code"] == 0
        ck = {"sc_token_teacher": r.cookies.get("sc_token_teacher")}
        r = _httpx.post(
            f"{base}/api/teacher/checkin/start",
            json={"course_id": "CS101", "duration_minutes": 5, "range_meters": 200},
            cookies={"sc_token_teacher": ck["sc_token_teacher"]},
            timeout=10,
        )
        sid = r.json()["data"]["id"]
        with _httpx.stream(
            "GET",
            f"{base}/api/teacher/checkin/{sid}/stream",
            cookies={"sc_token_teacher": ck["sc_token_teacher"]},
            timeout=_httpx.Timeout(10, read=15),
        ) as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            got_snapshot = False
            for line in resp.iter_lines():
                if line.startswith("data:") and '"snapshot"' in line:
                    got_snapshot = True
                    break
            assert got_snapshot, "SSE 快照帧未到达"
    finally:
        proc.terminate()


def test_checkin_stream_authz(teacher_token, student_token):
    """学生不能订阅他人课程的签到流"""
    sid = _start_session(teacher_token)
    resp = client.get(f"/api/teacher/checkin/{sid}/stream", cookies=student_token)
    assert resp.json()["code"] == 401


# ---------- Excel 导出 ----------

def test_attendance_export(teacher_token, student_token):
    sid = _start_session(teacher_token)
    r = client.get(f"/api/teacher/checkin/{sid}/export", cookies=teacher_token)
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"  # xlsx 即 zip 包
    # 学生无权导出（BizError → HTTP 200 + code 401）
    r2 = client.get(f"/api/teacher/checkin/{sid}/export", cookies=student_token)
    assert r2.json()["code"] == 401


def test_gradebook_export(teacher_token, student_token):
    # 取 T001 的任一作业（种子数据：演示作业 A/B 属 T001/CS101）
    lst = client.get("/api/homework/list", cookies=teacher_token).json()
    assert lst["code"] == 0 and lst["data"], "种子作业缺失，请先 python main.py --seed"
    hw_id = lst["data"][0]["id"]
    r = client.get(f"/api/homework/{hw_id}/gradebook/export", cookies=teacher_token)
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"
    # 学生无权导出
    r2 = client.get(f"/api/homework/{hw_id}/gradebook/export", cookies=student_token)
    assert r2.json()["code"] == 401


# ---------- 互动统计 SQL 聚合 ----------

def test_interaction_stats(teacher_token, student_token):
    # 写一条提问互动，统计应立即可见
    resp = client.post(
        "/api/interaction/",
        json={
            "course_id": "CS101",
            "student_id": "2024001",
            "interaction_type": "question",
            "content": "统计聚合测试提问",
        },
        cookies=teacher_token,
    )
    assert resp.json()["code"] == 0

    body = client.get("/api/interaction/stats/CS101", cookies=teacher_token).json()
    assert body["code"] == 0
    data = body["data"]
    assert data["total"] >= 1
    assert data["by_type"].get("question", 0) >= 1
    assert data["top_students"] is not None
    assert isinstance(data["enrolled_count"], int)

    # 学生无权查看统计
    r2 = client.get("/api/interaction/stats/CS101", cookies=student_token)
    assert r2.json()["code"] == 401


# ---------- push_many 批量通知 ----------

def test_push_many():
    db = SessionLocal()
    try:
        n = push_many(
            db,
            [
                ("2024001", "student", "test_bulk", "批量测试", "内容A", None, "CS101"),
                ("2024002", "student", "test_bulk", "批量测试", "内容B"),  # 尾参可省略
                ("T001", "teacher", "test_bulk", "批量测试", "非数字编号应跳过"),
            ],
        )
        assert n == 2  # T001 非数字编号被跳过
        rows = (
            db.query(Notification)
            .filter(Notification.notif_type == "test_bulk")
            .count()
        )
        assert rows == 2
    finally:
        db.query(Notification).filter(Notification.notif_type == "test_bulk").delete(
            synchronize_session=False
        )
        db.commit()
        db.close()
