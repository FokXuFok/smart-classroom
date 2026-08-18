# -*- coding: utf-8 -*-
"""AI 模块测试：chat 请求构造与降级路径（mock httpx）+ 答疑真实调用（可 skip）
+ 热词统计（不调 LLM）+ 知识库 CRUD 循环

沙箱策略（模块级）：记录 ai_qa_record / ai_knowledge_base / ai_scoring_rule
的 max(id)，teardown 删除 id > max 的自建数据。
"""
import datetime
import os

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core import ai_client
from app.core.ai_client import AiUnavailable
from app.database import SessionLocal
from app.main import app
from app.models import AiKnowledgeBase, AiQaRecord, AiScoringRule
from tests.conftest import forge_cookies, login_cookies

client = TestClient(app)

STUDENT = "2024001"
NO_AI = os.environ.get("SC_NO_AI") == "1"

STATE = {}  # 跨用例共享：qa record_id / hotword ids / kb_id

BASE_MAXES = {}


@pytest.fixture(scope="module")
def teacher_token():
    return login_cookies("T001", "123456", "teacher")


@pytest.fixture(scope="module")
def student_token():
    return login_cookies(STUDENT, "123456", "student")


@pytest.fixture(scope="module", autouse=True)
def db_sandbox():
    db = SessionLocal()
    try:
        BASE_MAXES["qa"] = db.query(func.max(AiQaRecord.id)).scalar() or 0
        BASE_MAXES["kb"] = db.query(func.max(AiKnowledgeBase.id)).scalar() or 0
        BASE_MAXES["rule"] = db.query(func.max(AiScoringRule.id)).scalar() or 0
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        db.query(AiQaRecord).filter(AiQaRecord.id > BASE_MAXES["qa"]).delete(
            synchronize_session=False
        )
        db.query(AiKnowledgeBase).filter(
            AiKnowledgeBase.id > BASE_MAXES["kb"]
        ).delete(synchronize_session=False)
        db.query(AiScoringRule).filter(
            AiScoringRule.id > BASE_MAXES["rule"]
        ).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


# ---------- t1 chat 请求构造（mock httpx client） ----------

class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeClient:
    """记录请求并返回预设响应的假 httpx.Client"""

    def __init__(self, response=None, exc=None):
        self.calls = []
        self._response = response
        self._exc = exc

    def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self._exc is not None:
            raise self._exc
        return self._response


def test_t1_chat_request_shape(monkeypatch):
    fake = FakeClient(
        FakeResponse({"choices": [{"message": {"content": "你好"}}]})
    )
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)

    messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}]
    out = ai_client.chat(messages, temperature=0.55, max_tokens=123)

    assert out == "你好"
    assert len(fake.calls) == 1
    call = fake.calls[0]
    assert call["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert call["json"]["model"] == ai_client.config.AI_MODEL
    assert call["json"]["messages"] == messages
    assert call["json"]["temperature"] == 0.55
    assert call["json"]["max_tokens"] == 123
    assert call["headers"]["Authorization"].startswith("Bearer ")


# ---------- t2 AiUnavailable 路径：超时 / 非200 / choices 空 ----------

def test_t2a_chat_timeout(monkeypatch):
    monkeypatch.setattr(
        ai_client,
        "_get_client",
        lambda: FakeClient(exc=httpx.TimeoutException("timed out")),
    )
    with pytest.raises(AiUnavailable):
        ai_client.chat([{"role": "user", "content": "hi"}])


def test_t2b_chat_http_error(monkeypatch):
    fake = FakeClient(FakeResponse({"error": "denied"}, status_code=401))
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)
    with pytest.raises(AiUnavailable) as ei:
        ai_client.chat([{"role": "user", "content": "hi"}])
    assert "401" in str(ei.value)


def test_t2c_chat_empty_choices(monkeypatch):
    fake = FakeClient(FakeResponse({"choices": []}))
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)
    with pytest.raises(AiUnavailable):
        ai_client.chat([{"role": "user", "content": "hi"}])


# ---------- t3 答疑 API：真实调用百炼（不可用则 skip） ----------

@pytest.mark.skipif(NO_AI, reason="SC_NO_AI=1 跳过真实 AI 调用")
def test_t3_qa_real(student_token):
    resp = client.post(
        "/api/ai/qa",
        json={
            "course_id": "CS101",
            "question": "什么是变量",
            "is_anonymous": True,
        },
        cookies=student_token,
    )
    body = resp.json()
    if body["code"] == 6001:
        pytest.skip(f"百炼服务不可用：{body.get('message')}")
    assert body["code"] == 0, body

    answer = body["data"]["answer"]
    record_id = body["data"]["record_id"]
    assert isinstance(answer, str) and answer.strip()
    STATE["qa_record_id"] = record_id

    db = SessionLocal()
    try:
        row = db.get(AiQaRecord, record_id)
        assert row is not None, "答疑记录未落库"
        assert row.course_id == "CS101"
        assert row.student_id == STUDENT
        assert row.answer == answer
        assert row.is_anonymous == 1
    finally:
        db.close()


# ---------- t4 热词统计（不调 LLM） ----------

def test_t4_hotwords(teacher_token):
    db = SessionLocal()
    try:
        rows = [
            AiQaRecord(
                course_id="CS101",
                student_id=STUDENT,
                question=q,
                answer="测试答案",
                is_anonymous=0,
                create_time=datetime.datetime.now(),
            )
            for q in ("python 变量是什么", "python 循环怎么写", "变量命名规则")
        ]
        db.add_all(rows)
        db.commit()
        STATE["hotword_ids"] = [r.id for r in rows]
    finally:
        db.close()

    resp = client.get(
        "/api/ai/qa/hotwords",
        params={"course_id": "CS101"},
        cookies=teacher_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    words = body["data"]
    assert isinstance(words, list) and len(words) <= 10
    assert all(set(w) == {"word", "count"} for w in words)
    assert any(w["word"] == "变量" for w in words), words
    assert any(w["word"] == "python" for w in words), words


# ---------- t5 知识库 CRUD 循环：POST→GET→PUT→DELETE ----------

def test_t5_knowledge_crud(teacher_token):
    # POST
    resp = client.post(
        "/api/ai/knowledge",
        json={
            "course_id": "CS101",
            "title": "pytest-变量知识点",
            "content": "变量是内存中一块命名的存储空间",
        },
        cookies=teacher_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    kb_id = body["data"]["id"]
    STATE["kb_id"] = kb_id

    # GET
    resp = client.get(
        "/api/ai/knowledge",
        params={"course_id": "CS101"},
        cookies=teacher_token,
    )
    items = resp.json()["data"]
    kb = next(k for k in items if k["id"] == kb_id)
    assert kb["title"] == "pytest-变量知识点"
    assert kb["status"] == 1

    # PUT
    resp = client.put(
        "/api/ai/knowledge",
        json={"id": kb_id, "title": "pytest-变量知识点v2", "content": "更新后的内容"},
        cookies=teacher_token,
    )
    assert resp.json()["code"] == 0
    resp = client.get(
        "/api/ai/knowledge",
        params={"course_id": "CS101"},
        cookies=teacher_token,
    )
    kb = next(k for k in resp.json()["data"] if k["id"] == kb_id)
    assert kb["title"] == "pytest-变量知识点v2"
    assert kb["content"] == "更新后的内容"

    # DELETE
    resp = client.delete(
        "/api/ai/knowledge", params={"id": kb_id}, cookies=teacher_token
    )
    assert resp.json()["code"] == 0
    resp = client.get(
        "/api/ai/knowledge",
        params={"course_id": "CS101"},
        cookies=teacher_token,
    )
    assert all(k["id"] != kb_id for k in resp.json()["data"])
    STATE.pop("kb_id", None)  # 已自删，teardown 无需再清


# ---------- t6 学生答疑历史：匿名脱敏 ----------

def test_t6_qa_history_anonymous_masked(student_token):
    resp = client.get(
        "/api/ai/qa/history",
        params={"course_id": "CS101", "limit": 20},
        cookies=student_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    rows = body["data"]
    # 匿名记录不回显真实学号
    for r in rows:
        if r["is_anonymous"]:
            assert r["student_id"] == "匿名"
            assert r["student_id"] != STUDENT
        else:
            assert r["student_id"] == STUDENT


# ---------- t7 越权回归（审查修复后补充） ----------

@pytest.fixture()
def t002_token():
    # T002 不授课 CS101（属 T001）
    return forge_cookies("T002", "teacher", "李沛")


@pytest.fixture()
def cs101_rule_id(teacher_token):
    """绑定 CS101 的评分规则（属 T001）；teardown 清理"""
    resp = client.post(
        "/api/ai/rules",
        json={
            "course_id": "CS101",
            "name": "pytest-CS101评分规则",
            "content": "正确实现函数逻辑得满分",
        },
        cookies=teacher_token,
    )
    body = resp.json()
    assert body["code"] == 0, body
    rule_id = body["data"]["id"]
    yield rule_id
    db = SessionLocal()
    try:
        rule = db.get(AiScoringRule, rule_id)
        if rule is not None:
            db.delete(rule)
            db.commit()
    finally:
        db.close()


def test_t7a_hotwords_denied_for_student(student_token):
    resp = client.get(
        "/api/ai/qa/hotwords",
        params={"course_id": "CS101"},
        cookies=student_token,
    )
    assert resp.json()["code"] == 403


def test_t7b_hotwords_denied_for_other_teacher(teacher_token, t002_token):
    resp = client.get(
        "/api/ai/qa/hotwords",
        params={"course_id": "CS101"},  # 属 T001
        cookies=t002_token,
    )
    assert resp.json()["code"] == 403
    # 属主 T001 正常访问
    resp = client.get(
        "/api/ai/qa/hotwords",
        params={"course_id": "CS101"},
        cookies=teacher_token,
    )
    assert resp.json()["code"] == 0


def test_t7c_rules_denied_for_other_teacher(t002_token, cs101_rule_id):
    # T002 修改绑定 CS101 的规则（属 T001）→ 403
    resp = client.put(
        "/api/ai/rules",
        json={"id": cs101_rule_id, "name": "越权篡改"},
        cookies=t002_token,
    )
    assert resp.json()["code"] == 403
    # T002 删除同一条规则 → 403
    resp = client.delete(
        f"/api/ai/rules/{cs101_rule_id}",
        cookies=t002_token,
    )
    assert resp.json()["code"] == 403
