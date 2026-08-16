# -*- coding: utf-8 -*-
"""评测计分与输出归一化纯逻辑测试"""
from app.core.judge.service import (
    compute_weighted_score,
    normalize_output,
    rule_feedback,
    similarity_3gram,
    tokenize_code,
)


# ---------- normalize_output ----------

def test_normalize_trailing_spaces():
    assert normalize_output("3  \n30\n") == "3\n30"


def test_normalize_blank_lines():
    assert normalize_output("\n\n3\n30\n\n\n") == "3\n30"


def test_normalize_crlf_and_empty():
    assert normalize_output("a\r\n\r\nb\r\n") == "a\n\nb"
    assert normalize_output("") == ""
    assert normalize_output(None) == ""


# ---------- 权重计分 ----------

def test_weighted_score_full():
    # 两用例权重 0.4/0.6，全过 → 100
    assert compute_weighted_score(1.0, 1.0, 100) == 100.0


def test_weighted_score_partial_60_40():
    # 权重计分 60*0.4+40*0.6 的镜像：只过 0.6 权重用例 → 60
    assert compute_weighted_score(0.6, 1.0, 100) == 60.0
    # 只过 0.4 权重用例 → 40
    assert compute_weighted_score(0.4, 1.0, 100) == 40.0


def test_weighted_score_contributions_sum():
    # 权重 0.6/0.4 的两个用例：分项贡献 60 与 40，合计满分
    a = compute_weighted_score(0.6, 1.0, 100)
    b = compute_weighted_score(0.4, 1.0, 100)
    assert a == 60.0 and b == 40.0 and a + b == 100.0


def test_weighted_score_zero_weight_degenerate():
    # 权重和为 0 → 按通过用例数比例
    assert compute_weighted_score(0, 0, 100, passed_count=1, total_count=2) == 50.0
    assert compute_weighted_score(0, 0, 100, passed_count=0, total_count=2) == 0.0


def test_weighted_score_no_cases():
    assert compute_weighted_score(0, 0, 100) == 0.0


# ---------- 规则反馈 ----------

def test_rule_feedback_content():
    results = [
        {"case_id": 1, "name": "公开用例", "passed": True, "stdout": "3",
         "expected": "3", "stderr": "", "time_ms": 12},
        {"case_id": 2, "name": "隐藏用例", "passed": False, "stdout": "999",
         "expected": "30", "stderr": "", "time_ms": 10},
    ]
    fb = rule_feedback(results, 40.0)
    assert "40" in fb
    assert "1/2" in fb
    assert "隐藏用例" in fb
    assert "30" in fb and "999" in fb
    assert "改进建议" in fb


def test_rule_feedback_all_pass():
    results = [{"case_id": 1, "name": "t", "passed": True, "stdout": "3",
                "expected": "3", "stderr": "", "time_ms": 5}]
    assert "全部用例通过" in rule_feedback(results, 100.0)


# ---------- 查重基础 ----------

def test_similarity_identical():
    code = "a, b = map(int, input().split())\nprint(a + b)"
    sim, matched = similarity_3gram(code, code)
    assert sim == 1.0
    assert matched > 0


def test_similarity_different():
    sim, _ = similarity_3gram("print(1)", "x = [1,2,3]\nprint(sum(x))")
    assert sim < 0.5


def test_tokenize_strips_comments_and_blank():
    tokens = tokenize_code("# 注释\nprint(1)  // 行注释\n\n")
    assert "#" not in tokens
    assert tokens == ["print", "(", "1", ")"]
