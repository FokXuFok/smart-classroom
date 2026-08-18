# -*- coding: utf-8 -*-
"""AI 客户端：阿里百炼（OpenAI 兼容接口，deepseek-V4-pro）
任何失败（网络/超时/Key无效/限流）→ AiUnavailable，由调用方降级"""
import json
import time

import httpx

import config
from app.core.logger import get_logger

logger = get_logger("app.ai")


class AiUnavailable(Exception):
    """AI 服务不可用（网络/超时/Key无效/限流/响应异常）"""


_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    """懒加载单例（timeout=60）"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(timeout=60)
    return _client


def chat(messages: list, temperature: float = 0.3, max_tokens: int = 2000) -> str:
    """POST {AI_BASE_URL}/chat/completions，返回首条回复文本；
    非 200 / choices 空 / 任何异常 → AiUnavailable（含简短原因）"""
    url = f"{config.AI_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": config.AI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        # 关闭思考模式：避免推理 token 耗尽 max_tokens 导致只返回截断的思考文本
        "enable_thinking": False,
    }
    headers = {"Authorization": f"Bearer {config.AI_API_KEY}"}
    started = time.perf_counter()
    try:
        resp = _get_client().post(url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning(
            "AI 调用失败(网络) model=%s 耗时=%.1fs 错误=%s",
            config.AI_MODEL, time.perf_counter() - started, type(exc).__name__,
        )
        raise AiUnavailable(f"网络错误: {type(exc).__name__}")
    if resp.status_code != 200:
        logger.warning(
            "AI 调用失败(HTTP %s) model=%s 耗时=%.1fs",
            resp.status_code, config.AI_MODEL, time.perf_counter() - started,
        )
        raise AiUnavailable(f"HTTP {resp.status_code}: {resp.text[:200]}")
    try:
        data = resp.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") == "length":
            raise AiUnavailable("AI 输出被截断(max_tokens)")
        content = choice["message"].get("content")
    except AiUnavailable:
        logger.warning(
            "AI 输出被截断 model=%s max_tokens=%s", config.AI_MODEL, max_tokens
        )
        raise
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        logger.warning(
            "AI 响应格式异常 model=%s: %s", config.AI_MODEL, type(exc).__name__
        )
        raise AiUnavailable(f"响应格式异常: {type(exc).__name__}")
    if not content:
        logger.warning("AI 返回空内容 model=%s", config.AI_MODEL)
        raise AiUnavailable("模型返回空内容")
    logger.info(
        "AI 调用成功 model=%s 耗时=%.1fs 输入=%d条 输出=%d字",
        config.AI_MODEL, time.perf_counter() - started,
        len(messages), len(content),
    )
    return content


def is_available() -> bool:
    """探活：能成功完成一次最小对话即视为可用"""
    try:
        chat([{"role": "user", "content": "ok"}], max_tokens=4)
    except AiUnavailable:
        return False
    return True


# ---- 学科 Agent 批改（judge/service.py 调用，签名必须兼容！）----

def grade_feedback(
    code, language, results, score, max_score, scoring_rules=None
) -> str:
    """学科作业批改 Agent：基于测试结果与踩分点生成学生可读的 markdown 反馈；
    失败 raise AiUnavailable（service.py 会降级 rule_feedback）"""
    language = language or "python"
    passed = sum(1 for r in results if r.get("passed"))
    system = (
        f"你是{language}学科作业批改Agent，只能在{language}学科范围内推理，"
        "严格依据给定测试结果与踩分点评判，不得臆造未提供的信息。"
        "请将发现的错误归类为 syntax/logic/runtime/boundary/performance 之一。"
        "输出 markdown，依次包含小节：##得分分析、##逐用例点评、##错误诊断、##改进建议；"
        "语言面向学生、具体可操作，全文 600 字以内。"
    )
    if scoring_rules:
        rule_lines = "\n".join(f"- {r}" for r in scoring_rules)
        system += f"\n本作业踩分点/评分规则：\n{rule_lines}"
    user = (
        f"## 学生代码（{language}）\n```\n{code or ''}\n```\n\n"
        f"## 测试结果（通过 {passed}/{len(results)}）\n"
        f"```json\n{json.dumps(results, ensure_ascii=False, indent=1)[:4000]}\n```\n\n"
        f"## 得分\n{score} / {max_score}"
    )
    return chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=2500,
    )


# ---- 学生答疑 ----

def qa_answer(course_name: str, knowledge: list, question: str) -> str:
    """课程助教答疑：优先基于课程知识片段回答；超纲问题礼貌说明并给学习建议"""
    if knowledge:
        kb = "\n\n".join(
            f"[课程资料{i}] {k}" for i, k in enumerate(knowledge, start=1)
        )
        system = (
            f"你是《{course_name}》课程助教。请仅基于以下课程知识片段回答学生问题，"
            f"用中文回答，控制在 200 字以内；若问题超出课程知识范围，"
            "请礼貌说明并给出下一步学习建议。\n\n"
            f"{kb}"
        )
    else:
        system = (
            f"你是《{course_name}》课程助教。当前没有可引用的课程资料，"
            "请凭该学科通用常识回答学生问题，用中文，控制在 200 字以内，"
            "并在回答开头注明：（非课程资料答案）"
        )
    return chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ],
        temperature=0.3,
        max_tokens=800,
    )


# ---- 教师备课助手 ----

def teacher_assist(course_name: str, topic: str) -> str:
    """备课材料：课堂提问建议 / 知识点解析 / 易错点提醒"""
    system = (
        f"你是《{course_name}》课程的教师备课助手。针对给定主题生成备课材料，"
        "用中文输出 markdown，依次包含：##课堂提问建议（3 个问题，每个附参考答案）、"
        "##知识点解析、##易错点提醒。"
    )
    return chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"备课主题：{topic}"},
        ],
        temperature=0.4,
        max_tokens=2000,
    )


# ---- 班级错误统计汇总 ----

def analyze_errors(homework_title, language, wrong_summary: list) -> str:
    """班级高频错误统计 + 讲评建议（输入为学生错误样本摘要列表）"""
    system = (
        f"你是{language}编程教学数据分析助手。根据学生错误样本摘要，"
        "归纳班级高频错误并给出讲评建议，用中文输出 markdown，依次包含："
        "##高频错误统计（错误类型、出现频次、典型表现）、##讲评建议。"
    )
    samples = "\n".join(
        f"{i}. {s}" for i, s in enumerate(wrong_summary, start=1)
    )[:4000]
    user = f"作业：{homework_title}（{language}）\n学生错误样本摘要：\n{samples}"
    return chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        max_tokens=1500,
    )
