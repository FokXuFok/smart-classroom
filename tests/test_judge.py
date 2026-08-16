# -*- coding: utf-8 -*-
"""评测运行器纯逻辑测试（无 API / 无数据库）"""
import shutil

import pytest

from app.core.judge.runner import DockerRunner, LocalProcessRunner, get_runner

runner = get_runner()


def test_get_runner_returns_local():
    assert isinstance(get_runner(), LocalProcessRunner)


# ---------- python 基础执行 ----------

def test_python_simple_output():
    r = runner.run("print(1+1)", "python", "")
    assert r["ok"] is True
    assert r["stdout"].strip() == "2"
    assert r["time_ms"] >= 0


def test_python_stdin_read():
    code = "name = input()\nprint('hello', name)"
    r = runner.run(code, "python", "tom\n")
    assert r["ok"] is True
    assert r["stdout"].strip() == "hello tom"


# ---------- 黑名单 ----------

def test_python_blocklist_import_os():
    r = runner.run("import os\nprint(os.getcwd())", "python", "")
    assert r["ok"] is False
    assert "禁止" in r["stderr"]


def test_python_blocklist_open():
    r = runner.run("open('/etc/passwd')", "python", "")
    assert r["ok"] is False
    assert "禁止" in r["stderr"]


def test_python_blocklist_importlib():
    r = runner.run("import importlib\nprint(1)", "python", "")
    assert r["ok"] is False
    assert "禁止" in r["stderr"]


def test_python_blocklist_import_not_at_line_start():
    # 非行首 import（分号/缩进后）同样拦截
    r = runner.run("x = 1;import os\nprint(os.getcwd())", "python", "")
    assert r["ok"] is False
    assert "禁止" in r["stderr"]


def test_c_blocklist_system():
    r = runner.run(
        '#include <stdlib.h>\nint main(){system("ls");return 0;}', "c", ""
    )
    assert r["ok"] is False
    assert "禁止" in r["stderr"]


def test_c_open_not_blocked():
    # open( 只拦 Python：C 使用 fopen 不再被误杀（无 gcc 时应报工具链错误而非禁止）
    r = runner.run(
        '#include <stdio.h>\n'
        'int main(){FILE *f=fopen("x.txt","r");return f?0:1;}',
        "c",
        "",
    )
    assert "禁止" not in r["stderr"]


def test_java_blocklist_processbuilder():
    r = runner.run(
        "public class Main { public static void main(String[] args) "
        "{ new ProcessBuilder(\"ls\"); } }",
        "java",
        "",
    )
    assert r["ok"] is False
    assert "禁止" in r["stderr"]


# ---------- 超时 ----------

def test_python_timeout():
    r = runner.run("while True:\n    pass", "python", "", time_limit_ms=500)
    assert r["ok"] is False
    assert "超时" in r["stderr"]


# ---------- C 工具链探测 ----------

def test_c_language():
    if shutil.which("gcc") is None:
        # 本机无 gcc：应返回可读错误而非崩溃
        r = runner.run(
            '#include <stdio.h>\nint main(){printf("hello");return 0;}',
            "c",
            "",
        )
        assert r["ok"] is False
        assert "gcc/g++" in r["stderr"]
    else:
        r = runner.run(
            '#include <stdio.h>\nint main(){int a,b;scanf("%d %d",&a,&b);'
            'printf("%d",a+b);return 0;}',
            "c",
            "1 2\n",
        )
        assert r["ok"] is True
        assert r["stdout"].strip() == "3"


def test_java_language():
    code = (
        "public class Main { public static void main(String[] args) "
        '{ System.out.println("hello"); } }'
    )
    if shutil.which("javac") is None:
        r = runner.run(code, "java", "")
        assert r["ok"] is False
        assert "JDK" in r["stderr"] or "javac" in r["stderr"]
    else:
        r = runner.run(code, "java", "")
        assert r["ok"] is True
        assert r["stdout"].strip() == "hello"


# ---------- 输出截断 ----------

def test_output_truncation():
    r = runner.run(
        "print('x' * (100 * 1024))", "python", ""
    )
    assert r["ok"] is True
    assert len(r["stdout"]) <= LocalProcessRunner.MAX_OUTPUT + 100
    assert "截断" in r["stdout"]


# ---------- 其他 ----------

def test_empty_code():
    r = runner.run("   \n", "python", "")
    assert r["ok"] is False


def test_unsupported_language():
    r = runner.run("print(1)", "ruby", "")
    assert r["ok"] is False
    assert "不支持" in r["stderr"]


def test_docker_runner_placeholder():
    with pytest.raises(NotImplementedError):
        DockerRunner().run("print(1)", "python", "")
