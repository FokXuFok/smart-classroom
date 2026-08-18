# -*- coding: utf-8 -*-
"""统一业务异常与响应包装"""
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.logger import get_logger


class BizError(Exception):
    """业务异常：code 非 0，HTTP 层始终返回 200"""

    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def ok(data=None, message: str = "ok"):
    """统一成功响应体"""
    return {"code": 0, "message": message, "data": data}


# 常用错误码约定（全项目统一使用）：
# 401 未认证/登录失效  403 无权限  400 参数错误  404 不存在
# 1001 密码错误(已锁定则提示锁定)  1002 账号锁定中  1003 账号被禁用
# 2001 人脸未注册  2002 人脸相似度不足  2003 超出签到范围  2004 无进行中签到会话
# 2005 重复签到  2006 会话已结束  3001 评测失败  3002 截止后禁止提交
# 5000 服务器内部错误  6001 AI服务不可用(降级提示)


def register_exception_handlers(app: FastAPI) -> None:
    """把 BizError / 未捕获异常转为统一 JSON（HTTP 始终 200，业务码区分）"""

    @app.exception_handler(BizError)
    async def biz_error_handler(request, exc: BizError):
        return JSONResponse(
            status_code=200, content={"code": exc.code, "message": exc.message}
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request, exc: Exception):
        get_logger("app.error").exception(
            "未捕获异常 %s %s: %s",
            request.method,
            request.url.path,
            exc,
        )
        # 细节仅落服务端日志，不向客户端回显（避免泄露 SQL/路径等内部信息）
        return JSONResponse(
            status_code=200,
            content={"code": 5000, "message": "服务器内部错误"},
        )
