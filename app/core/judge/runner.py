# -*- coding: utf-8 -*-
"""代码评测运行器：本地进程隔离（默认）+ Docker（预留）"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time


class LocalProcessRunner:
    """本地子进程评测：独立临时目录+超时+输出截断+源码黑名单

    language: python / c / cpp / java
    """

    MAX_OUTPUT = 64 * 1024
    PY_BLOCKLIST = [  # Python 黑名单（正则，匹配源码则拒绝执行）
        r"\bimport\s+(os|sys|subprocess|shutil|socket|ctypes|requests|urllib|importlib)\b",
        r"\bfrom\s+(os|sys|subprocess|shutil|socket|ctypes|requests|urllib|importlib)\b",
        r"__import__",
        r"eval\s*\(",
        r"exec\s*\(",
        r"open\s*\(",
        r"importlib",
        r"compile\s*\(",
    ]
    C_BLOCKLIST = [r"\bsystem\s*\(", r"\bpopen\s*\(", r"\bexecl\b"]
    JAVA_BLOCKLIST = [r"ProcessBuilder", r"Runtime\.getRuntime"]
    BLOCKLIST_MSG = "代码包含禁止调用的模块/函数"

    # ---------- 内部工具 ----------

    def _check_blocklist(self, code: str, language: str) -> bool:
        """按语言选择黑名单表（open( 等只拦 Python，避免误杀 C 的 fopen）"""
        if language in ("c", "cpp"):
            patterns = self.C_BLOCKLIST
        elif language == "java":
            patterns = self.JAVA_BLOCKLIST
        else:
            patterns = self.PY_BLOCKLIST
        for pattern in patterns:
            if re.search(pattern, code, flags=re.MULTILINE):
                return True
        return False

    def _truncate(self, text: str) -> str:
        if text is None:
            return ""
        if len(text) > self.MAX_OUTPUT:
            return (
                text[: self.MAX_OUTPUT]
                + "\n...[输出超出 %d 字节，已截断]" % self.MAX_OUTPUT
            )
        return text

    def _run_process(self, args, cwd, stdin_text, timeout_s):
        """执行子进程并统一转成 {ok, stdout, stderr, time_ms}"""
        start = time.time()
        try:
            proc = subprocess.run(
                args,
                cwd=cwd,
                input=stdin_text or "",
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": "运行超时", "time_ms": 0}
        except Exception as exc:  # 启动失败等
            return {
                "ok": False,
                "stdout": "",
                "stderr": str(exc),
                "time_ms": 0,
            }
        time_ms = int((time.time() - start) * 1000)
        return {
            "ok": proc.returncode == 0,
            "stdout": self._truncate(proc.stdout or ""),
            "stderr": self._truncate(proc.stderr or ""),
            "time_ms": time_ms,
        }

    # ---------- 各语言执行 ----------

    def _run_python(self, code, stdin_text, time_limit_ms, tmpdir):
        src = os.path.join(tmpdir, "main.py")
        with open(src, "w", encoding="utf-8") as f:
            f.write(code)
        timeout_s = max(time_limit_ms / 1000, 1) + 0.5
        return self._run_process(
            [sys.executable, "-I", "main.py"], tmpdir, stdin_text, timeout_s
        )

    def _compile_and_run(self, code, language, stdin_text, time_limit_ms, tmpdir):
        if language in ("c", "cpp"):
            compiler = shutil.which("gcc" if language == "c" else "g++")
            if not compiler:
                return {
                    "ok": False,
                    "stdout": "",
                    "stderr": "本机未安装 gcc/g++ 工具链，无法评测 C/C++ 作业",
                    "time_ms": 0,
                }
            suffix = "c" if language == "c" else "cpp"
            src = os.path.join(tmpdir, "main." + suffix)
            exe = os.path.join(tmpdir, "main")
            with open(src, "w", encoding="utf-8") as f:
                f.write(code)
            compiled = self._run_process(
                [compiler, src, "-o", exe], tmpdir, "", 10
            )
            if not compiled["ok"]:
                return {
                    "ok": False,
                    "stdout": "",
                    "stderr": compiled["stderr"] or "编译失败",
                    "time_ms": compiled["time_ms"],
                }
            timeout_s = max(time_limit_ms / 1000, 1) + 0.5
            return self._run_process([exe], tmpdir, stdin_text, timeout_s)

        if language == "java":
            javac = shutil.which("javac")
            java = shutil.which("java")
            if not javac or not java:
                return {
                    "ok": False,
                    "stdout": "",
                    "stderr": "本机未安装 JDK 工具链（javac/java），无法评测 Java 作业",
                    "time_ms": 0,
                }
            src = os.path.join(tmpdir, "Main.java")
            with open(src, "w", encoding="utf-8") as f:
                f.write(code)
            compiled = self._run_process([javac, "Main.java"], tmpdir, "", 10)
            if not compiled["ok"]:
                return {
                    "ok": False,
                    "stdout": "",
                    "stderr": compiled["stderr"] or "编译失败",
                    "time_ms": compiled["time_ms"],
                }
            timeout_s = max(time_limit_ms / 1000, 1) + 0.5
            return self._run_process(
                [java, "-cp", ".", "Main"], tmpdir, stdin_text, timeout_s
            )

        return {
            "ok": False,
            "stdout": "",
            "stderr": f"不支持的编程语言: {language}",
            "time_ms": 0,
        }

    # ---------- 对外入口 ----------

    def run(self, code, language, stdin_text, time_limit_ms=1000) -> dict:
        """返回 {ok, stdout, stderr, time_ms}"""
        language = (language or "python").lower()
        if not code or not code.strip():
            return {"ok": False, "stdout": "", "stderr": "源代码为空", "time_ms": 0}

        # 源码黑名单（按语言分表检查）
        if self._check_blocklist(code, language):
            return {
                "ok": False,
                "stdout": "",
                "stderr": self.BLOCKLIST_MSG,
                "time_ms": 0,
            }

        tmpdir = tempfile.mkdtemp(prefix="judge_")
        try:
            if language == "python":
                return self._run_python(code, stdin_text, time_limit_ms, tmpdir)
            return self._compile_and_run(
                code, language, stdin_text, time_limit_ms, tmpdir
            )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class DockerRunner:
    """Docker 沙箱运行器（预留）：安装 Docker 后将 run() 改为

    docker run --rm --network=none --memory 256m -v {dir}:/src {image} ...
    当前未实现。
    """

    def run(self, code, language, stdin_text, time_limit_ms=1000) -> dict:
        raise NotImplementedError(
            "Docker Runner 预留，当前环境使用本地进程隔离"
        )


def get_runner() -> LocalProcessRunner:
    """全局唯一入口，未来可按配置切换"""
    return LocalProcessRunner()
