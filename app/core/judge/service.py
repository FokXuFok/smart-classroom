# -*- coding: utf-8 -*-
"""评测流水线：判分 + 成绩册 upsert + AI 反馈（降级规则反馈）+ 代码查重"""
import datetime
import json
import re

from app.core.judge.runner import get_runner
from app.database import SessionLocal
from app.models import (
    CodeSimilarity,
    GradeBook,
    Homework,
    SubmissionRecord,
    TestCase,
)

SIMILARITY_THRESHOLD = 0.80


def normalize_output(s: str) -> str:
    """每行 rstrip，去首尾空行"""
    if not s:
        return ""
    lines = [line.rstrip() for line in s.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def compute_weighted_score(
    passed_weight: float,
    total_weight: float,
    max_score: float,
    passed_count: int = 0,
    total_count: int = 0,
) -> float:
    """score = max_score * Σ(通过用例 weight)/Σ(全部 weight)；
    权重和为 0 时退化为按通过用例数比例计分"""
    if total_weight > 0:
        ratio = passed_weight / total_weight
    elif total_count > 0:
        ratio = passed_count / total_count
    else:
        ratio = 0.0
    return round(float(max_score or 0) * ratio, 2)


def rule_feedback(results: list, score: float) -> str:
    """规则降级反馈：按用例通过率生成中文 markdown"""
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    lines = [
        "### 评测反馈（规则生成）",
        "",
        f"- **总得分**：{score} 分（通过用例 {passed}/{total}）",
        "",
    ]
    if total:
        lines.append("| 用例 | 结果 | 耗时 |")
        lines.append("| --- | --- | --- |")
        for r in results:
            mark = "✅ 通过" if r.get("passed") else "❌ 未通过"
            lines.append(
                f"| {r.get('name') or r.get('case_id')} | {mark} | {r.get('time_ms', 0)}ms |"
            )
        lines.append("")
    for r in results:
        if r.get("passed"):
            continue
        lines.append(f"**未通过用例：{r.get('name') or r.get('case_id')}**")
        lines.append("")
        if r.get("is_public") is False:
            # 隐藏用例：不向学生展示期望/实际输出，防止答案泄露
            lines.append("- 该用例为隐藏测试点，请检查边界条件、特殊输入与输出格式")
        else:
            expected = str(r.get("expected") or "")[:200]
            actual = str(r.get("stdout") or "")[:200]
            stderr = str(r.get("stderr") or "")[:200]
            lines.append(f"- 期望输出：`{expected}`")
            lines.append(f"- 实际输出：`{actual}`")
            if stderr:
                lines.append(f"- 错误信息：`{stderr}`")
        lines.append("")
    if passed == total and total > 0:
        lines.append("全部用例通过，继续保持！可尝试优化代码的时间与空间开销。")
    else:
        lines.append(
            "**改进建议**：请对照失败用例的期望输出与实际输出，检查边界条件、"
            "输出格式（多余空格/换行）与算法逻辑；也可请教老师或同学讨论思路。"
        )
    return "\n".join(lines)


def judge_submission(submission_id: int, count_submit: bool = True) -> None:
    """评测单条提交（独立 DB 会话，可被 BackgroundTasks / 重评接口调用）

    count_submit=False 用于重评：不累加 grade_book.submit_count
    """
    db = SessionLocal()
    try:
        submission = (
            db.query(SubmissionRecord)
            .filter(SubmissionRecord.id == submission_id)
            .first()
        )
        if submission is None:
            return
        homework = db.get(Homework, submission.homework_id)
        if homework is None:
            return
        cases = (
            db.query(TestCase)
            .filter(TestCase.homework_id == homework.id)
            .order_by(TestCase.order_num, TestCase.id)
            .all()
        )

        language = homework.programming_language or "python"
        max_score = float(homework.max_score or 100)

        # 1) 无用例：直接 0 分完成
        if not cases:
            submission.score = 0
            submission.status = 1
            submission.test_results = json.dumps([])
            submission.judge_time = datetime.datetime.now()
            db.commit()
            _upsert_gradebook(db, submission, 0, count_submit)
            _attach_feedback(db, submission, homework, [], 0)
            return

        # 2) 逐用例执行
        runner = get_runner()
        results = []
        for case in cases:
            try:
                outcome = runner.run(
                    submission.submitted_code or "",
                    language,
                    case.test_input or "",
                    case.time_limit or 1000,
                )
            except NotImplementedError:
                outcome = {"ok": False, "stdout": "", "stderr": "运行器未实现", "time_ms": 0}
            except Exception as exc:  # runner 崩溃不应中断整条流水线
                outcome = {"ok": False, "stdout": "", "stderr": str(exc), "time_ms": 0}
            passed = bool(outcome.get("ok")) and normalize_output(
                outcome.get("stdout") or ""
            ) == normalize_output(case.expected_output or "")
            results.append(
                {
                    "case_id": case.id,
                    "name": case.name,
                    "passed": passed,
                    "stdout": outcome.get("stdout") or "",
                    "expected": case.expected_output or "",
                    "stderr": outcome.get("stderr") or "",
                    "time_ms": outcome.get("time_ms") or 0,
                    "is_public": bool(case.is_public),
                }
            )

        # 3) 编译错误归类（stderr 含 error 且全部失败）
        all_failed = all(not r["passed"] for r in results)
        compile_error = None
        if all_failed:
            for r in results:
                if "error" in (r["stderr"] or "").lower():
                    compile_error = (r["stderr"] or "")[:2000]
                    break

        # 4) 计分
        passed_weight = sum(
            float(c.score_weight or 0)
            for c, r in zip(cases, results)
            if r["passed"]
        )
        total_weight = sum(float(c.score_weight or 0) for c in cases)
        score = compute_weighted_score(
            passed_weight,
            total_weight,
            max_score,
            passed_count=sum(1 for r in results if r["passed"]),
            total_count=len(results),
        )

        submission.status = 1
        submission.score = score
        submission.test_results = json.dumps(results, ensure_ascii=False)
        submission.compile_error = compile_error
        submission.judge_time = datetime.datetime.now()
        db.commit()

        # 5) 成绩册 upsert（历史最高分，提交次数 +1）
        _upsert_gradebook(db, submission, score, count_submit)

        # 6) AI 反馈（任何异常都降级为规则反馈）
        _attach_feedback(db, submission, homework, results, score)
    finally:
        db.close()


def _upsert_gradebook(
    db, submission: SubmissionRecord, score: float, count_submit: bool = True
) -> None:
    gb = (
        db.query(GradeBook)
        .filter(
            GradeBook.homework_id == submission.homework_id,
            GradeBook.student_id == submission.student_id,
        )
        .first()
    )
    now = datetime.datetime.now()
    if gb is None:
        db.add(
            GradeBook(
                course_id=submission.course_id,
                homework_id=submission.homework_id,
                student_id=submission.student_id,
                score=score,
                submit_count=1 if count_submit else 0,
                judge_time=now,
                create_time=now,
                update_time=now,
            )
        )
    else:
        gb.score = max(float(gb.score or 0), score)
        if count_submit:
            gb.submit_count = (gb.submit_count or 0) + 1
        gb.judge_time = now
        gb.update_time = now
    db.commit()


def _attach_feedback(db, submission, homework, results, score) -> None:
    try:
        from app.core.ai_client import grade_feedback

        # 传给 AI 的结果同样过滤隐藏用例的期望/实际输出，防止反馈文本复述答案
        public_results = [
            {k: v for k, v in r.items() if k not in ("expected", "stdout")}
            if r.get("is_public") is False
            else r
            for r in results
        ]
        feedback = grade_feedback(
            submission.submitted_code,
            homework.programming_language,
            public_results,
            score,
            homework.max_score,
        )
    except Exception:
        feedback = rule_feedback(results, score)
    submission.ai_feedback = feedback
    submission.status = 2
    db.commit()
    # 通知钩子：批改完成通知学生（push 内部自带异常兜底，不影响评测主流程）
    try:
        from app.api.notification import push

        push(
            db,
            submission.student_id,
            "student",
            "homework_graded",
            "作业已批改",
            f"您的作业「{homework.title}」已完成批改，得分 {score} 分，可查看反馈详情。",
            related_id=submission.id,
            course_id=submission.course_id,
        )
    except Exception:
        pass


# ---------- 代码查重 ----------

_COMMENT_LINE = re.compile(r"#.*|//.*")
_COMMENT_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_TOKEN = re.compile(r"\w+|[^\w\s]")


def tokenize_code(code: str) -> list:
    """去注释/空白后切词法 token（查重前归一化）"""
    if not code:
        return []
    code = _COMMENT_BLOCK.sub(" ", code)
    code = "\n".join(_COMMENT_LINE.sub(" ", line) for line in code.split("\n"))
    return _TOKEN.findall(code)


def similarity_3gram(code_a: str, code_b: str) -> tuple:
    """3-gram Jaccard 相似度；返回 (similarity, matched_fingerprint_count)"""
    tokens_a = tokenize_code(code_a)
    tokens_b = tokenize_code(code_b)
    if not tokens_a or not tokens_b:
        return 0.0, 0
    grams_a = {" ".join(tokens_a[i : i + 3]) for i in range(len(tokens_a) - 2)}
    grams_b = {" ".join(tokens_b[i : i + 3]) for i in range(len(tokens_b) - 2)}
    if not grams_a or not grams_b:
        return 0.0, 0
    matched = grams_a & grams_b
    union = grams_a | grams_b
    return round(len(matched) / len(union), 4), len(matched)


def check_homework_similarity(homework_id: int) -> list:
    """取该作业每个学生最高分提交，两两 3-gram Jaccard，
    >0.80 upsert CodeSimilarity（student_a_id < student_b_id 字典序）"""
    db = SessionLocal()
    try:
        submissions = (
            db.query(SubmissionRecord)
            .filter(SubmissionRecord.homework_id == homework_id)
            .order_by(SubmissionRecord.score.desc(), SubmissionRecord.id.desc())
            .all()
        )
        best: dict = {}
        for sub in submissions:
            if sub.student_id not in best:
                best[sub.student_id] = sub
        subs = sorted(best.values(), key=lambda s: s.student_id)

        now = datetime.datetime.now()
        pairs = []
        for i in range(len(subs)):
            for j in range(i + 1, len(subs)):
                a, b = subs[i], subs[j]
                # 保证字典序 a < b
                if a.student_id > b.student_id:
                    a, b = b, a
                sim, matched = similarity_3gram(
                    a.submitted_code or "", b.submitted_code or ""
                )
                if sim <= SIMILARITY_THRESHOLD:
                    continue
                row = (
                    db.query(CodeSimilarity)
                    .filter(
                        CodeSimilarity.homework_id == homework_id,
                        CodeSimilarity.student_a_id == a.student_id,
                        CodeSimilarity.student_b_id == b.student_id,
                    )
                    .first()
                )
                if row is None:
                    row = CodeSimilarity(
                        homework_id=homework_id,
                        student_a_id=a.student_id,
                        student_b_id=b.student_id,
                    )
                    db.add(row)
                row.similarity = sim
                row.matched_fingerprint_count = matched
                row.submission_a_id = a.id
                row.submission_b_id = b.id
                row.check_time = now
                pairs.append(
                    {
                        "student_a_id": a.student_id,
                        "student_b_id": b.student_id,
                        "similarity": sim,
                        "matched_fingerprint_count": matched,
                        "submission_a_id": a.id,
                        "submission_b_id": b.id,
                    }
                )
        db.commit()
        pairs.sort(key=lambda p: p["similarity"], reverse=True)
        return pairs
    finally:
        db.close()
