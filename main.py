# -*- coding: utf-8 -*-
"""全流程智慧课堂系统 一键启动
用法: python main.py [--seed] [--no-browser] [--port 8000]

流程：依赖检查(缺失自动 pip 安装) → 数据库连通检查 → 增量建表(幂等)
     → [可选 --seed] 演示种子数据 → 启动 uvicorn → [可选] 自动打开浏览器
兼容任意 Python 解释器（自动使用当前解释器补装依赖）。
"""
import argparse
import importlib.util
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

try:  # Windows 控制台中文友好
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# (import 模块名, pip 包名)
REQUIRED = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("sqlalchemy", "sqlalchemy"),
    ("pymysql", "pymysql"),
    ("bcrypt", "bcrypt"),
    ("jwt", "PyJWT"),
    ("httpx", "httpx"),
    ("cv2", "opencv-python"),
    ("numpy", "numpy"),
    ("insightface", "insightface"),
    ("onnxruntime", "onnxruntime"),
    ("openpyxl", "openpyxl"),
]

BANNER = r"""
============================================================
          全流程智慧课堂系统  Smart Classroom
============================================================
"""


def check_deps() -> None:
    """逐个检查必需依赖；缺失则用当前解释器自动 pip 安装"""
    missing = [pip for mod, pip in REQUIRED if importlib.util.find_spec(mod) is None]
    if not missing:
        print("[OK]    依赖检查通过（fastapi/uvicorn/sqlalchemy/... 全部就绪）")
        return
    print(f"[WARN]  缺失依赖：{missing}，正在自动安装（清华镜像）...")
    cmd = [
        sys.executable, "-m", "pip", "install", "-r",
        str(BASE_DIR / "requirements.txt"),
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
    ]
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as exc:
        print(f"[FAIL]  自动安装依赖失败（exit={exc.returncode}）。")
        print("        请手动执行：python -m pip install -r requirements.txt")
        sys.exit(1)
    still = [pip for mod, pip in REQUIRED if importlib.util.find_spec(mod) is None]
    if still:
        print(f"[FAIL]  安装后仍缺失：{still}，请手动安装后重试")
        sys.exit(1)
    print("[OK]    依赖安装完成")


def check_database() -> None:
    """MySQL 连通性检查（使用 config.DB_URL）"""
    from sqlalchemy import text

    import config
    from app.database import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"[FAIL]  数据库连接失败：{type(exc).__name__}: {exc}")
        print("        请确认 MySQL 已启动且账号配置正确（.env 中 DB_URL：")
        print(f"        {config.DB_URL}）")
        sys.exit(1)
    print("[OK]    数据库连接正常")


def load_script(rel_path: str):
    """scripts/ 无 __init__.py，按文件路径加载模块"""
    path = BASE_DIR / rel_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def print_startup_banner(port: int) -> None:
    print(BANNER)
    print(f"  服务地址      http://127.0.0.1:{port}")
    print(f"  门户/登录页   http://127.0.0.1:{port}/index.html")
    print(f"  学生端        http://127.0.0.1:{port}/student.html")
    print(f"  教师端        http://127.0.0.1:{port}/teacher.html")
    print(f"  辅导员端      http://127.0.0.1:{port}/counselor.html")
    print(f"  管理端        http://127.0.0.1:{port}/admin.html")
    print("  ----------------------------------------------------------")
    print("  演示账号：admin/admin123 · T001/123456 · C001/123456")
    print("            学生 2024001~2024004 / 123456")
    print("  ----------------------------------------------------------")
    print("  停止服务：Ctrl+C")
    print("============================================================")


def preheat_face_engine() -> None:
    """后台线程预热 InsightFace 人脸模型（约 280MB）。

    避免演示时第一次人脸签到请求现场加载模型卡顿数秒；
    放在启动器而非 app/main.py：pytest 导入应用时不会触发，测试零干扰。
    """
    def _load():
        try:
            from app.core.face_engine import get_engine

            get_engine()
            print("[OK]    人脸模型预热完成（首次人脸签到无需等待）")
        except Exception as exc:
            print(f"[WARN]  人脸模型预热失败（首次签到时将再次尝试加载）：{exc}")

    threading.Thread(target=_load, daemon=True, name="face-preheat").start()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="全流程智慧课堂系统 一键启动"
                    "（依赖自动安装 · 数据库增量升级 · 静态页面托管）"
    )
    parser.add_argument(
        "--seed", action="store_true",
        help="启动前写入演示种子数据（幂等，人员数据不受影响）",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="启动后不自动打开浏览器",
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="监听端口（默认 8000）",
    )
    args = parser.parse_args()

    check_deps()
    check_database()

    print("[RUN ]  执行数据库增量升级（幂等，不删改已有数据）...")
    init_db = load_script("scripts/init_db.py")
    init_db.main()

    if args.seed:
        print("[RUN ]  写入演示种子数据（幂等）...")
        seed_demo = load_script("scripts/seed_demo.py")
        seed_demo.main()

    print_startup_banner(args.port)
    # 与 uvicorn 启动并行预热人脸模型，演示时首次签到秒响应
    preheat_face_engine()

    if not args.no_browser:
        url = f"http://127.0.0.1:{args.port}/"
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        print(f"[TIP]   1.5 秒后将自动打开浏览器：{url}")

    import uvicorn
    from app.main import app

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
