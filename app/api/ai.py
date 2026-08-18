# -*- coding: utf-8 -*-
"""AI 模块 API：学生答疑 / 教师备课助手 / 热词统计 / 批改全量 / 知识库 / 评分规则"""
import asyncio
import datetime
import json
import re
from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_

from app.api.deps import CurrentUser, get_db, require_roles
from app.core.ai_client import (
    AiUnavailable,
    grade_feedback,
    qa_answer,
    teacher_assist,
)
from app.core.exception import BizError, ok
from app.core.judge.service import rule_feedback
from app.core.logger import get_logger
from app.models import (
    AiKnowledgeBase,
    AiQaRecord,
    AiScoringRule,
    Course,
    Enrollment,
    Homework,
    SubmissionRecord,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])

KNOWLEDGE_SNIPPET_MAX = 500  # 单条知识片段送入 AI 的截断长度
GRADE_CONCURRENCY = 4  # 全量批改的最大并发 AI 调用数（兼顾等待时间与 AI 配额）

grade_log = get_logger("app.ai")


# ---------- 请求模型 ----------

class QaAskReq(BaseModel):
    course_id: str
    question: str
    is_anonymous: bool = True


class TeacherAssistReq(BaseModel):
    course_id: str
    topic: str


class KnowledgeCreateReq(BaseModel):
    course_id: str
    title: str
    content: str = ""
    subject: Optional[str] = None
    difficulty: int = 1
    sort_order: int = 0


class KnowledgeUpdateReq(BaseModel):
    """全可选（id 必填）"""

    id: int
    title: Optional[str] = None
    content: Optional[str] = None
    subject: Optional[str] = None
    difficulty: Optional[int] = None
    sort_order: Optional[int] = None
    status: Optional[int] = None


class RuleCreateReq(BaseModel):
    course_id: Optional[str] = None  # 空 = 通用规则
    name: str
    content: str
    subject: Optional[str] = None
    rule_type: str = "score_point"  # score_point / deduct
    weight: float = 0
    max_score: float = 0
    criteria: Optional[str] = None
    sort_order: int = 0
    status: int = 1


class RuleUpdateReq(BaseModel):
    """全可选（id 必填）"""

    id: int
    course_id: Optional[str] = None
    name: Optional[str] = None
    content: Optional[str] = None
    subject: Optional[str] = None
    rule_type: Optional[str] = None
    weight: Optional[float] = None
    max_score: Optional[float] = None
    criteria: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[int] = None


# ---------- 公共校验 ----------

def _get_owned_course(db, course_id: str, teacher_no: str) -> Course:
    course = db.query(Course).filter(Course.course_code == course_id).first()
    if course is None:
        raise BizError(404, "课程不存在")
    if course.teacher_id != teacher_no:
        raise BizError(403, "无权限操作该课程")
    return course


def _ai_unavailable() -> BizError:
    return BizError(6001, "AI 服务暂不可用，请稍后再试")


# ---------- 学生端：答疑 ----------

@router.post("/qa")
def ai_qa_ask(
    req: QaAskReq,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    course = db.query(Course).filter(Course.course_code == req.course_id).first()
    if course is None:
        raise BizError(404, "课程不存在")
    enrolled = (
        db.query(Enrollment)
        .filter(
            Enrollment.course_id == req.course_id,
            Enrollment.student_id == current.user.student_no,
            Enrollment.status == 1,
        )
        .first()
    )
    if enrolled is None:
        raise BizError(403, "未选修该课程")

    knowledges = (
        db.query(AiKnowledgeBase)
        .filter(
            AiKnowledgeBase.course_id == req.course_id,
            AiKnowledgeBase.status == 1,
        )
        .order_by(AiKnowledgeBase.id.desc())
        .limit(3)
        .all()
    )
    snippets = [
        (k.content or "")[:KNOWLEDGE_SNIPPET_MAX]
        for k in knowledges
        if k.content
    ]

    # 答疑必须生成答案，不降级：AI 不可用直接报 6001
    try:
        answer = qa_answer(
            course.course_name or req.course_id, snippets, req.question
        )
    except AiUnavailable:
        raise _ai_unavailable()

    record = AiQaRecord(
        course_id=req.course_id,
        student_id=current.user.student_no,
        question=req.question,
        answer=answer,
        is_anonymous=1 if req.is_anonymous else 0,
        create_time=datetime.datetime.now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ok(
        {"answer": answer, "record_id": record.id}, message="回答生成成功"
    )


@router.get("/qa/history")
def ai_qa_history(
    course_id: str,
    limit: int = 20,
    current: CurrentUser = Depends(require_roles("student")),
    db=Depends(get_db),
):
    """本人提问 + 本课匿名提问（匿名记录不回显真实学号）"""
    rows = (
        db.query(AiQaRecord)
        .filter(
            AiQaRecord.course_id == course_id,
            or_(
                AiQaRecord.student_id == current.user.student_no,
                AiQaRecord.is_anonymous == 1,
            ),
        )
        .order_by(AiQaRecord.id.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    data = [
        {
            "id": r.id,
            "question": r.question,
            "answer": r.answer,
            "is_anonymous": bool(r.is_anonymous),
            "student_id": "匿名" if r.is_anonymous else r.student_id,
            "create_time": r.create_time,
        }
        for r in rows
    ]
    return ok(data)


# ---------- 教师端：备课助手 / 热词 ----------

@router.post("/teacher/assist")
def ai_teacher_assist(
    req: TeacherAssistReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    course = _get_owned_course(db, req.course_id, current.user.teacher_no)
    try:
        content = teacher_assist(course.course_name or req.course_id, req.topic)
    except AiUnavailable:
        raise _ai_unavailable()
    return ok({"course_id": req.course_id, "topic": req.topic, "content": content})


_WORD_RUN = re.compile(r"[\u4e00-\u9fff]+|[A-Za-z0-9_]+")
_STOPWORDS = {
    "什么", "怎么", "怎样", "如何", "为何", "为什么", "哪个", "哪些",
    "这个", "那个", "这些", "那些", "请问", "一下", "可以", "应该",
    "还是", "如果", "但是", "然后", "时候", "老师", "同学", "我们",
    "你们", "他们", "自己", "现在", "可能", "就是", "还有", "没有",
    "不是", "一个", "一些", "关于", "或者", "以及", "之后", "之前",
}


def _tokenize_question(text: str) -> list:
    """中文按 2-gram 切分，英文/数字按整词，去停用词（不依赖分词库）"""
    tokens = []
    for run in _WORD_RUN.findall(text or ""):
        if run.isascii():
            tokens.append(run.lower())
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return [t for t in tokens if len(t) >= 2 and t not in _STOPWORDS]


@router.get("/qa/hotwords")
def ai_qa_hotwords(
    course_id: str,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    _get_owned_course(db, course_id, current.user.teacher_no)
    questions = [
        q
        for (q,) in db.query(AiQaRecord.question).filter(
            AiQaRecord.course_id == course_id
        )
    ]
    counter: Counter = Counter()
    for text in questions:
        counter.update(_tokenize_question(text))
    top10 = counter.most_common(10)
    return ok([{"word": w, "count": c} for w, c in top10])


# ---------- 教师端：整作业 AI 批改 ----------

@router.post("/homework/{homework_id}/grade-all")
async def ai_grade_all(
    homework_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    """对已评测（status in 1,2）的提交批量生成 AI 反馈：
    成功 → ai_feedback/status=2 计 graded；
    AiUnavailable → 降级 rule_feedback 计 degraded；
    其他异常 → 跳过计 failed（不重新评测，只做反馈）

    异步 + 有界并发：AI 网络调用交线程池并行，降低整体等待；
    数据库会话仅在聚合完成后于主线程写回，避免跨线程共享连接。"""
    hw = db.get(Homework, homework_id)
    if hw is None:
        raise BizError(404, "作业不存在")
    if hw.teacher_id != current.user.teacher_no:
        raise BizError(403, "无权限操作该作业")

    submissions = (
        db.query(SubmissionRecord)
        .filter(
            SubmissionRecord.homework_id == hw.id,
            SubmissionRecord.status.in_([1, 2]),
        )
        .all()
    )
    submissions = submissions[:20]  # 单次批量上限，防止长时间占用 AI 配额
    sem = asyncio.Semaphore(GRADE_CONCURRENCY)

    async def _gen(sub) -> tuple:
        try:
            results = json.loads(sub.test_results or "[]")
        except ValueError:
            results = []
        # 隐藏用例剥离 expected/stdout，防止 AI 反馈复述答案
        public_results = [
            {
                k: v
                for k, v in r.items()
                if k not in ("expected", "stdout")
            }
            if r.get("is_public") is False
            else r
            for r in results
        ]
        async with sem:
            try:
                feedback = await asyncio.to_thread(
                    grade_feedback,
                    sub.submitted_code,
                    hw.programming_language,
                    public_results,
                    sub.score,
                    hw.max_score,
                )
                return sub, "graded", feedback
            except AiUnavailable:
                feedback = await asyncio.to_thread(
                    rule_feedback, results, sub.score or 0
                )
                return sub, "degraded", feedback
            except Exception:
                return sub, "failed", None

    outcomes = await asyncio.gather(*(_gen(s) for s in submissions))
    graded = failed = degraded = 0
    for sub, kind, feedback in outcomes:
        if kind == "failed":
            failed += 1
            continue
        if kind == "graded":
            graded += 1
        else:
            degraded += 1
        sub.ai_feedback = feedback
        sub.status = 2
    db.commit()
    grade_log.info(
        "AI 批量批改完成 homework=%s 提交=%d 成功=%d 降级=%d 失败=%d",
        homework_id, len(submissions), graded, degraded, failed,
    )
    return ok(
        {"graded": graded, "failed": failed, "degraded": degraded},
        message=(
            f"AI 批改完成：成功 {graded}，降级 {degraded}，失败 {failed}"
            "（单次最多批改 20 条，可重复调用）"
        ),
    )


# ---------- 教师端：知识库 CRUD ----------

def _knowledge_dict(k: AiKnowledgeBase) -> dict:
    return {
        "id": k.id,
        "course_id": k.course_id,
        "subject": k.subject,
        "title": k.title,
        "content": k.content,
        "difficulty": k.difficulty,
        "sort_order": k.sort_order,
        "status": k.status,
        "create_time": k.create_time,
        "update_time": k.update_time,
    }


def _check_knowledge_owned(db, kb: AiKnowledgeBase, teacher_no: str) -> None:
    """通用知识点（course_id 为空）任意教师可维护；绑定课程则校验归属"""
    if kb.course_id:
        _get_owned_course(db, kb.course_id, teacher_no)


@router.get("/knowledge")
def list_knowledge(
    course_id: str = "",
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    q = db.query(AiKnowledgeBase)
    if course_id:
        q = q.filter(AiKnowledgeBase.course_id == course_id)
    rows = q.order_by(
        AiKnowledgeBase.sort_order, AiKnowledgeBase.id.desc()
    ).all()
    return ok([_knowledge_dict(k) for k in rows])


@router.post("/knowledge")
def create_knowledge(
    req: KnowledgeCreateReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    _get_owned_course(db, req.course_id, current.user.teacher_no)
    now = datetime.datetime.now()
    kb = AiKnowledgeBase(
        course_id=req.course_id,
        subject=req.subject,
        title=req.title,
        content=req.content,
        difficulty=req.difficulty,
        sort_order=req.sort_order,
        status=1,
        create_time=now,
        update_time=now,
    )
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return ok({"id": kb.id}, message="知识点已创建")


@router.put("/knowledge")
def update_knowledge(
    req: KnowledgeUpdateReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    kb = db.get(AiKnowledgeBase, req.id)
    if kb is None:
        raise BizError(404, "知识点不存在")
    _check_knowledge_owned(db, kb, current.user.teacher_no)
    for field in (
        "title",
        "content",
        "subject",
        "difficulty",
        "sort_order",
        "status",
    ):
        value = getattr(req, field)
        if value is not None:
            setattr(kb, field, value)
    kb.update_time = datetime.datetime.now()
    db.commit()
    return ok({"id": kb.id}, message="知识点已更新")


@router.delete("/knowledge")
def delete_knowledge(
    id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    kb = db.get(AiKnowledgeBase, id)
    if kb is None:
        raise BizError(404, "知识点不存在")
    _check_knowledge_owned(db, kb, current.user.teacher_no)
    db.delete(kb)
    db.commit()
    return ok({"id": id}, message="知识点已删除")


# ---------- 教师端：评分规则 CRUD（course_id 为空即通用规则，允许跨课） ----------

def _rule_dict(r: AiScoringRule) -> dict:
    return {
        "id": r.id,
        "course_id": r.course_id,
        "subject": r.subject,
        "name": r.name,
        "content": r.content,
        "weight": r.weight,
        "sort_order": r.sort_order,
        "status": r.status,
        "rule_type": r.rule_type,
        "max_score": r.max_score,
        "criteria": r.criteria,
        "create_time": r.create_time,
        "update_time": r.update_time,
    }


@router.get("/rules")
def list_rules(
    course_id: str = "",
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    q = db.query(AiScoringRule)
    if course_id:
        q = q.filter(AiScoringRule.course_id == course_id)
    rows = q.order_by(AiScoringRule.sort_order, AiScoringRule.id.desc()).all()
    return ok([_rule_dict(r) for r in rows])


@router.post("/rules")
def create_rule(
    req: RuleCreateReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    if req.rule_type not in ("score_point", "deduct"):
        raise BizError(400, "rule_type 仅支持 score_point/deduct")
    now = datetime.datetime.now()
    rule = AiScoringRule(
        course_id=req.course_id,
        subject=req.subject,
        name=req.name,
        content=req.content,
        weight=req.weight,
        sort_order=req.sort_order,
        status=req.status,
        rule_type=req.rule_type,
        max_score=req.max_score,
        criteria=req.criteria,
        create_time=now,
        update_time=now,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return ok({"id": rule.id}, message="评分规则已创建")


def _check_rule_owned(db, rule: AiScoringRule, teacher_no: str) -> None:
    """通用规则（course_id 为空）任意教师可维护；绑定课程则校验归属"""
    if rule.course_id:
        _get_owned_course(db, rule.course_id, teacher_no)


@router.put("/rules")
def update_rule(
    req: RuleUpdateReq,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    rule = db.get(AiScoringRule, req.id)
    if rule is None:
        raise BizError(404, "评分规则不存在")
    _check_rule_owned(db, rule, current.user.teacher_no)
    if req.course_id is not None and req.course_id != rule.course_id:
        # 迁移规则到新课程同样需要目标课程归属
        _get_owned_course(db, req.course_id, current.user.teacher_no)
    if req.rule_type is not None and req.rule_type not in (
        "score_point",
        "deduct",
    ):
        raise BizError(400, "rule_type 仅支持 score_point/deduct")
    for field in (
        "course_id",
        "name",
        "content",
        "subject",
        "rule_type",
        "weight",
        "max_score",
        "criteria",
        "sort_order",
        "status",
    ):
        value = getattr(req, field)
        if value is not None:
            setattr(rule, field, value)
    rule.update_time = datetime.datetime.now()
    db.commit()
    return ok({"id": rule.id}, message="评分规则已更新")


@router.delete("/rules/{rule_id}")
def delete_rule(
    rule_id: int,
    current: CurrentUser = Depends(require_roles("teacher")),
    db=Depends(get_db),
):
    rule = db.get(AiScoringRule, rule_id)
    if rule is None:
        raise BizError(404, "评分规则不存在")
    _check_rule_owned(db, rule, current.user.teacher_no)
    db.delete(rule)
    db.commit()
    return ok({"id": rule_id}, message="评分规则已删除")
