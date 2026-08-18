# -*- coding: utf-8 -*-
"""结构化日志：控制台 + 按天滚动文件（logs/app.log，保留 14 天）
每条日志携带 req_id（请求ID中间件注入），贯穿"签到/评测/AI"全链路，便于按请求排查。
用法：from app.core.logger import get_logger; logger = get_logger("app.xxx")
"""
import logging
import logging.handlers
import uuid
from contextvars import ContextVar

import config

# 当前请求 ID（middleware 设置；线程池/BackgroundTasks 中自动传播）
req_id_var: ContextVar[str] = ContextVar("req_id", default="-")

LOG_DIR = config.BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(req_id)s] %(name)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class RequestIdFilter(logging.Filter):
    """把当前请求 req_id 注入每条日志记录（格式串中的 %(req_id)s）"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.req_id = req_id_var.get()
        return True


def new_req_id() -> str:
    return uuid.uuid4().hex[:8]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def setup_logging() -> None:
    """初始化根日志器：控制台 + 按天滚动文件（重复调用安全）"""
    root = logging.getLogger()
    if getattr(root, "_smart_classroom_setup", False):
        return
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        LOG_FILE, when="midnight", backupCount=14, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(RequestIdFilter())

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(RequestIdFilter())

    root.addHandler(file_handler)
    root.addHandler(console)
    # uvicorn access log 与本格式重复且不带 req_id；httpx/httpcore 每次请求刷两行噪音
    # （AI 调用已在 ai_client 按业务语义记录），统一关闭
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("httpx").disabled = True
    logging.getLogger("httpcore").disabled = True
    root._smart_classroom_setup = True
    get_logger("app").info("日志系统就绪：文件=%s（按天滚动，保留14天）", LOG_FILE)
