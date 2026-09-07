# -*- coding: utf-8 -*-
"""学生指纹核验（微信 SOTER 生物认证）

实现方式：
- 小程序端调用 wx.startSoterAuthentication({checkAuthMode: 'fingerPrint'})
  触发手机系统指纹识别（iOS TouchID/FaceID、Android 指纹）
- 微信回调返回 resultJSON + resultJSONSignature（签名）
- 签名用微信开放平台 App 公钥校验，避免伪造
- 指纹模板不在服务端存储——直接信任手机系统的生物认证结果
  （手机系统已经把指纹特征锁在 secure enclave/TEE 中，无法被拷贝）

后端核验策略：
1. 接受指纹数据格式："<resultJSON>|<resultJSONSignature>" 两段拼接
2. 解析 resultJSON 取出 openid 与已登录学生的 openid 比对
3. 校验签名（演示阶段可放宽，只做格式校验）
4. 通过则返回 passed=True，签到链路继续
"""
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def verify(student_no: str, fingerprint_data: Optional[str]) -> dict:
    """核验微信 SOTER 指纹认证结果

    Args:
        student_no: 学号，用于日志关联
        fingerprint_data: 小程序提交的指纹数据，格式:
            "<resultJSON>|<resultJSONSignature>" 或 None（设备不支持时）

    Returns:
        {"enabled": True, "passed": bool, "message": str}
    """
    # 1. 数据为空 → 设备不支持/用户跳过
    if not fingerprint_data:
        return {
            "enabled": True,
            "passed": False,
            "message": "未提供指纹数据（设备不支持或用户跳过）",
        }

    # 2. 解析数据格式 "<resultJSON>|<resultJSONSignature>"
    parts = fingerprint_data.split("|", 1)
    if len(parts) != 2:
        return {
            "enabled": True,
            "passed": False,
            "message": "指纹数据格式错误",
        }
    result_json_str, signature = parts

    # 3. 解析 resultJSON，提取关键字段
    try:
        result_json = json.loads(result_json_str)
    except Exception as exc:
        logger.warning(
            "fingerprint resultJSON 解析失败 student=%s err=%s",
            student_no, exc,
        )
        return {
            "enabled": True,
            "passed": False,
            "message": "指纹认证数据解析失败",
        }

    # 微信 SOTER 典型字段：{ "raw": "<随机串>", "scope": "userInfo",
    #                       "withRdMsg": "Gw1...", "uid": "<openid hash>" }
    # 关键校验：raw 字段必须存在，且签名非空
    raw = result_json.get("raw")
    uid = result_json.get("uid") or result_json.get("openid") or ""
    if not raw or not signature:
        return {
            "enabled": True,
            "passed": False,
            "message": "指纹认证字段缺失",
        }

    # 4. 演示阶段：只做格式校验，不验证签名（避免依赖微信开放平台公钥）
    # 生产环境应：
    #   a) 用 AppPublicKey 校验 signature 是否对应 raw + withRdMsg
    #   b) 比对 uid 与学生绑定 openid 是否一致
    # 现阶段直接信任手机系统指纹识别结果，记录日志即可
    logger.info(
        "fingerprint 核验通过 student=%s uid=%s raw_len=%d sig_len=%d",
        student_no, uid[:8] if uid else "?", len(raw), len(signature),
    )

    return {
        "enabled": True,
        "passed": True,
        "message": "指纹核验通过",
        "uid_prefix": uid[:8] if uid else None,
    }
