# -*- coding: utf-8 -*-
"""学生指纹核验 —— 预留接口（申报书第三因子，硬件对接后启用）

未来对接方向：USB 指纹仪 SDK / 手机指纹 API（WebAuthn）
"""


def verify(student_no: str, fingerprint_data) -> dict:
    """指纹核验（预留）：硬件对接前恒返回未启用"""
    return {"enabled": False, "passed": None, "message": "指纹核验接口预留，暂未启用"}
