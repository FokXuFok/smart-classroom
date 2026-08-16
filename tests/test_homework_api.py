# -*- coding: utf-8 -*-
"""编程作业模块 API 集成测试（TestClient + 真实库）

清理策略（模块级）：setup 先清除早期遗留的悬挂行与 pytest- 残留作业，
再记录 homework/test_case/submission_record/grade_book/code_similarity
的 max(id)；teardown 按 FK 安全顺序删除 id > max 的自建数据。
"""
import datetime
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, text

from app.database import SessionLocal
from app.main import app
from app.models import (
    CodeSimilarity,
    Enrollment,
    GradeBook,
    Homework,
    SubmissionRecord,
)
from app.models.homework import TestCase as CaseModel  # 别名避免 pytest 误收集

client = TestClient(app)

STUDENT = "2024001"
STUDENT2 = "2024002"

CORRECT_CODE = "a, b = map(int, input().split())\nprint(a + b)"
# 半对代码：恰好通过公开用例（1*2+1=3），隐藏用例失败（10*20+1=201 != 30）
HALF_CODE = "a, b = map(int, input().split())\nprint(a * b + 1)"

STATE = {}  # 跨用例共享：hw_id / submission ids


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


@pytest.fixture(scope="module")
def student2_token():
    resp = client.post(
        "/api/auth/login",
        json={"username": STUDENT2, "password": "123456", "role": "student"},
    )
    assert resp.json()["code"] == 0
    return resp.json()["data"]["token"]


@pytest.fixture(scope="module", autouse=True)
def db_sandbox():
    """模块级沙箱：setup 清理历史遗留脏数据并记录 max(id)，teardown 只删自建数据。

    说明：库中存在早期开发遗留的悬挂 submission_record/grade_book 行，
    其 homework_id 指向已不存在的作业（会与新作业自增 id 撞车导致 RESTRICT
    删除失败），setup 先清除；标题 pytest- 开头的作业为本套测试历史残留。
    """
    db = SessionLocal()
    try:
        # 1) 本套测试的历史残留作业 + 悬挂引用行（homework 已不存在）
        db.execute(
            text(
                "DELETE FROM submission_record WHERE homework_id IN "
                "(SELECT id FROM homework WHERE title LIKE 'pytest-%') "
                "OR homework_id NOT IN (SELECT id FROM homework)"
            )
        )
        db.execute(
            text(
                "DELETE FROM grade_book WHERE homework_id IN "
                "(SELECT id FROM homework WHERE title LIKE 'pytest-%') "
                "OR homework_id NOT IN (SELECT id FROM homework)"
            )
        )
        db.execute(
            text(
                "DELETE FROM code_similarity WHERE homework_id IN "
                "(SELECT id FROM homework WHERE title LIKE 'pytest-%') "
                "OR homework_id NOT IN (SELECT id FROM homework)"
            )
        )
        db.execute(text("DELETE FROM test_case WHERE homework_id IN "
                        "(SELECT id FROM homework WHERE title LIKE 'pytest-%')"))
        db.execute(text("DELETE FROM homework WHERE title LIKE 'pytest-%'"))
        db.commit()

        # 2) 记录基线 max(id)
        maxes = {
            "hw": db.query(func.max(Homework.id)).scalar() or 0,
            "case": db.query(func.max(CaseModel.id)).scalar() or 0,
            "sub": db.query(func.max(SubmissionRecord.id)).scalar() or 0,
            "gb": db.query(func.max(GradeBook.id)).scalar() or 0,
            "sim": db.query(func.max(CodeSimilarity.id)).scalar() or 0,
        }
    finally:
        db.close()

    yield

    # 3) teardown：按外键安全顺序删除自建数据；无论成败都关闭会话
    db = SessionLocal()
    try:
        db.query(CodeSimilarity).filter(
            CodeSimilarity.id > maxes["sim"]
        ).delete(synchronize_session=False)
        db.query(SubmissionRecord).filter(
            SubmissionRecord.id > maxes["sub"]
        ).delete(synchronize_session=False)
        db.query(GradeBook).filter(GradeBook.id > maxes["gb"]).delete(
            synchronize_session=False
        )
        db.query(CaseModel).filter(CaseModel.id > maxes["case"]).delete(
            synchronize_session=False
        )
        db.query(Homework).filter(Homework.id > maxes["hw"]).delete(
            synchronize_session=False
        )
        db.commit()
    finally:
        db.close()


def create_homework(teacher_token, **extra):
    payload = {
        "course_id": "CS101",
        "title": "pytest-两数之和",
        "description": "读入两个整数输出它们的和",
        "programming_language": "python",
        "max_score": 100,
        "test_cases": [
            {
                "name": "公开-小数",
                "test_input": "1 2\n",
                "expected_output": "3\n",
                "score_weight": 0.4,
                "is_public": True,
            },
            {
                "name": "隐藏-大数",
                "test_input": "10 20\n",
                "expected_output": "30\n",
                "score_weight": 0.6,
                "is_public": False,
            },
        ],
    }
    payload.update(extra)
    resp = client.post("/api/homework/", json=payload, headers=auth(teacher_token))
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]["homework_id"]


def submit_code(token, hw_id, code):
    resp = client.post(
        f"/api/student/homework/{hw_id}/submit",
        json={"code": code, "language": "python"},
        headers=auth(token),
    )
    return resp.json()


def wait_judged(token, hw_id, submission_id, timeout=15):
    """轮询 my 接口直到该提交完成评测"""
    end = time.time() + timeout
    while time.time() < end:
        resp = client.get(
            f"/api/student/homework/{hw_id}/my", headers=auth(token)
        )
        body = resp.json()
        if body["code"] == 0:
            for s in body["data"]:
                if s["id"] == submission_id and s["status"] in (1, 2):
                    return s
        time.sleep(0.3)
    return None


# ---------- t1 教师创建作业（2 用例：公开 0.4 / 隐藏 0.6） ----------

def test_t1_create_homework(teacher_token):
    hw_id = create_homework(teacher_token)
    STATE["hw_id"] = hw_id

    resp = client.get(f"/api/homework/{hw_id}", headers=auth(teacher_token))
    data = resp.json()["data"]
    assert data["title"] == "pytest-两数之和"
    assert len(data["test_cases"]) == 2
    weights = sorted(c["score_weight"] for c in data["test_cases"])
    assert weights == [0.4, 0.6]

    # 教师列表可见
    resp = client.get(
        "/api/homework/list", params={"course_id": "CS101"},
        headers=auth(teacher_token),
    )
    items = resp.json()["data"]
    mine = next(h for h in items if h["id"] == hw_id)
    assert mine["test_case_count"] == 2


# ---------- t2 学生详情：公开可见 / 隐藏不可见 ----------

def test_t2_student_detail_case_visibility(teacher_token, student_token):
    resp = client.get(
        f"/api/student/homework/{STATE['hw_id']}", headers=auth(student_token)
    )
    assert resp.json()["code"] == 0
    cases = resp.json()["data"]["test_cases"]
    pub = next(c for c in cases if c["is_public"])
    hidden = next(c for c in cases if not c["is_public"])
    assert pub["test_input"] == "1 2\n"
    assert pub["expected_output"] == "3\n"
    assert "test_input" not in hidden
    assert "expected_output" not in hidden
    assert hidden["score_weight"] == 0.6
    assert hidden["name"]

    # 学生作业列表包含该作业
    resp = client.get(
        "/api/student/homework/list", headers=auth(student_token)
    )
    items = resp.json()["data"]
    assert any(h["id"] == STATE["hw_id"] for h in items)


# ---------- t3 提交正确代码 → 100 分 ----------

def test_t3_submit_correct(teacher_token, student_token):
    body = submit_code(student_token, STATE["hw_id"], CORRECT_CODE)
    assert body["code"] == 0, body
    sub_id = body["data"]["submission_id"]
    STATE["correct_sub"] = sub_id

    judged = wait_judged(student_token, STATE["hw_id"], sub_id)
    assert judged is not None, "评测超时未完成"
    assert judged["score"] == 100
    assert judged["status"] in (1, 2)
    assert len(judged["test_results"]) == 2
    assert all(t["passed"] for t in judged["test_results"])


# ---------- t4 半对代码 → 40 分（0.4*100） ----------

def test_t4_submit_half_correct(teacher_token, student_token):
    body = submit_code(student_token, STATE["hw_id"], HALF_CODE)
    assert body["code"] == 0, body
    sub_id = body["data"]["submission_id"]
    STATE["half_sub"] = sub_id

    judged = wait_judged(student_token, STATE["hw_id"], sub_id)
    assert judged is not None, "评测超时未完成"
    assert judged["score"] == 40
    passed = [t["passed"] for t in judged["test_results"]]
    assert passed == [True, False]


# ---------- t4b 学生 /my：隐藏用例不泄露 expected/stdout ----------

def test_t4b_hidden_case_result_no_leak(teacher_token, student_token):
    resp = client.get(
        f"/api/student/homework/{STATE['hw_id']}/my", headers=auth(student_token)
    )
    assert resp.json()["code"] == 0
    subs = resp.json()["data"]
    judged = next(s for s in subs if s["id"] == STATE["half_sub"])
    results = judged["test_results"]
    assert len(results) == 2

    hidden = next(t for t in results if t["name"] == "隐藏-大数")
    assert "expected" not in hidden
    assert "stdout" not in hidden
    assert hidden["passed"] is False
    assert "time_ms" in hidden

    # 公共用例保留 expected/stdout 供学生对照
    pub = next(t for t in results if t["name"] == "公开-小数")
    assert pub.get("expected") == "3\n"
    assert pub.get("stdout") is not None


# ---------- t5 教师提交列表 + 成绩簿最高分 ----------

def test_t5_teacher_submissions_and_gradebook(teacher_token):
    resp = client.get(
        f"/api/homework/{STATE['hw_id']}/submissions", headers=auth(teacher_token)
    )
    assert resp.json()["code"] == 0
    subs = resp.json()["data"]
    mine = [s for s in subs if s["student_id"] == STUDENT]
    assert len(mine) == 2  # 正确 + 半对
    scores = {s["score"] for s in mine}
    assert scores == {100.0, 40.0}

    resp = client.get(
        f"/api/homework/{STATE['hw_id']}/gradebook", headers=auth(teacher_token)
    )
    rows = resp.json()["data"]
    row = next(r for r in rows if r["student_id"] == STUDENT)
    assert row["score"] == 100  # 历史最高分
    assert row["submit_count"] == 2
    assert row["student_name"]


# ---------- t6 AI 反馈：降级规则文本非空；开放前学生不可见 ----------

def test_t6_ai_feedback_rule_fallback(teacher_token, student_token):
    # 教师视角：judge 后 ai_feedback 非空（AiUnavailable → rule_feedback 降级）
    resp = client.get(
        f"/api/homework/{STATE['hw_id']}/submissions", headers=auth(teacher_token)
    )
    subs = resp.json()["data"]
    fb = next(s["ai_feedback"] for s in subs if s["id"] == STATE["correct_sub"])
    assert fb  # 非空

    # 学生视角：feedback_visible=0 且未过 deadline → ai_feedback 隐藏
    resp = client.get(
        f"/api/student/homework/{STATE['hw_id']}/my", headers=auth(student_token)
    )
    mine = resp.json()["data"]
    correct = next(s for s in mine if s["id"] == STATE["correct_sub"])
    assert correct["ai_feedback"] is None
    assert correct["ai_feedback_hint"]

    # 教师提前开放 → 学生可见
    resp = client.post(
        f"/api/homework/{STATE['hw_id']}/open-feedback",
        headers=auth(teacher_token),
    )
    assert resp.json()["code"] == 0
    resp = client.get(
        f"/api/student/homework/{STATE['hw_id']}/my", headers=auth(student_token)
    )
    correct = next(
        s for s in resp.json()["data"] if s["id"] == STATE["correct_sub"]
    )
    assert correct["ai_feedback"]


# ---------- t7 查重：两学生相同代码 → 相似度 > 0.8 ----------

def test_t7_similarity(teacher_token, student2_token):
    # 确认 2024002 已选 CS101
    db = SessionLocal()
    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == "CS101",
            Enrollment.student_id == STUDENT2,
            Enrollment.status == 1,
        )
        .first()
    )
    db.close()
    assert enrolled is not None, "2024002 未选 CS101，测试前置不满足"

    body = submit_code(student2_token, STATE["hw_id"], CORRECT_CODE)
    assert body["code"] == 0, body
    STATE["student2_sub"] = body["data"]["submission_id"]
    judged = wait_judged(student2_token, STATE["hw_id"], STATE["student2_sub"])
    assert judged is not None and judged["score"] == 100

    resp = client.post(
        f"/api/homework/{STATE['hw_id']}/similarity",
        headers=auth(teacher_token),
    )
    assert resp.json()["code"] == 0
    pairs = resp.json()["data"]
    assert pairs, "应检出至少一对高相似提交"
    pair = next(
        p
        for p in pairs
        if {p["student_a_id"], p["student_b_id"]} == {STUDENT, STUDENT2}
    )
    assert pair["similarity"] > 0.8
    assert pair["matched_fingerprint_count"] > 0

    # 落库校验：student_a_id < student_b_id 字典序
    db = SessionLocal()
    row = (
        db.query(CodeSimilarity)
        .filter(CodeSimilarity.homework_id == STATE["hw_id"])
        .first()
    )
    db.close()
    assert row.student_a_id == STUDENT
    assert row.student_b_id == STUDENT2
    assert row.similarity > 0.8


# ---------- t8 截止作业 → 3002 ----------

def test_t8_deadline_reject(teacher_token, student_token):
    hw_id = create_homework(
        teacher_token,
        title="pytest-已截止作业",
        deadline=(datetime.datetime.now() - datetime.timedelta(hours=1)).isoformat(),
        allow_late_submit=False,
    )
    STATE["closed_hw_id"] = hw_id
    body = submit_code(student_token, hw_id, CORRECT_CODE)
    assert body["code"] == 3002


# ---------- t9 有提交的作业不可删；无提交可删 ----------

def test_t9_delete_rules(teacher_token, student_token):
    # 有提交记录 → 400
    resp = client.delete(
        f"/api/homework/{STATE['hw_id']}", headers=auth(teacher_token)
    )
    assert resp.json()["code"] == 400

    # 无提交 → 可删（用截止作业，其无提交记录）
    resp = client.delete(
        f"/api/homework/{STATE['closed_hw_id']}", headers=auth(teacher_token)
    )
    assert resp.json()["code"] == 0


# ---------- t10 更新作业（test_cases 全删重建）+ 重评 ----------

def test_t10_update_and_rejudge(teacher_token):
    resp = client.put(
        f"/api/homework/{STATE['hw_id']}",
        json={
            "description": "更新后的描述",
            "test_cases": [
                {
                    "name": "公开-小数v2",
                    "test_input": "1 2\n",
                    "expected_output": "3\n",
                    "score_weight": 0.5,
                    "is_public": True,
                },
                {
                    "name": "隐藏-大数v2",
                    "test_input": "10 20\n",
                    "expected_output": "30\n",
                    "score_weight": 0.5,
                    "is_public": False,
                },
            ],
        },
        headers=auth(teacher_token),
    )
    assert resp.json()["code"] == 0
    resp = client.get(
        f"/api/homework/{STATE['hw_id']}", headers=auth(teacher_token)
    )
    cases = resp.json()["data"]["test_cases"]
    assert [c["name"] for c in cases] == ["公开-小数v2", "隐藏-大数v2"]

    # 重评：3 条提交全部重新评测（TestClient 同步执行后台任务）
    resp = client.post(
        f"/api/homework/{STATE['hw_id']}/rejudge", headers=auth(teacher_token)
    )
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["rejudge_count"] == 3

    # 重评不虚增提交次数：STUDENT 仍为 2 次，成绩取历史最高分
    resp = client.get(
        f"/api/homework/{STATE['hw_id']}/gradebook", headers=auth(teacher_token)
    )
    rows = resp.json()["data"]
    row = next(r for r in rows if r["student_id"] == STUDENT)
    assert row["submit_count"] == 2
    assert row["score"] == 100
