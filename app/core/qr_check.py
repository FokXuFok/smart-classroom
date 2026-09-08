# -*- coding: utf-8 -*-
"""签到二维码核验：从学生自拍照中解码二维码并与会话 token 比对

机制（替代原两帧活体）：
- 教师发起签到 → 后端生成随机 qr_token 落库（每次签到都不同）
- 教师端通过 GET /api/teacher/checkin/{id}/qr 取得该 token 的二维码（SVG，投影到大屏）
- 学生拍照时把屏幕上的当前二维码与本人脸部一起拍入画面
- 本模块用 cv2.QRCodeDetector 从照片解码二维码，与会话 qr_token 比对，
  防"离线照片/翻拍旧照"代签
"""
import base64

import cv2
import numpy as np

QR_PREFIX = "SC:"  # 二维码内容前缀，避免误识别照片中其它普通二维码


def read_qr_text(image_b64: str) -> str:
    """从 base64 图片解码二维码文本；解析失败/无二维码 → "" """
    try:
        if image_b64.startswith("data:"):
            image_b64 = image_b64.split(",", 1)[-1]
        buf = np.frombuffer(base64.b64decode(image_b64), np.uint8)
        bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    except Exception:
        return ""
    if bgr is None:
        return ""
    try:
        data, _points, _ = cv2.QRCodeDetector().detectAndDecode(bgr)
    except Exception:
        return ""
    return (data or "").strip()


def check_qr(image_b64: str, qr_token: str) -> dict:
    """校验照片中的二维码是否与会话 token 匹配

    Args:
        image_b64: 学生自拍 base64（可带 data: URI 前缀）
        qr_token: 会话 checkin_session.qr_token

    Returns:
        {"passed": bool, "message": str}
    """
    expected = f"{QR_PREFIX}{qr_token}" if qr_token else ""
    if not expected:
        return {"passed": False, "message": "会话缺少二维码配置"}
    text = read_qr_text(image_b64)
    if not text:
        return {
            "passed": False,
            "message": "照片中未检测到二维码，请正对教师屏幕上的二维码拍摄",
        }
    if text != expected:
        return {
            "passed": False,
            "message": "二维码不匹配，请对准当前教师屏幕上的二维码重新拍摄",
        }
    return {"passed": True, "message": "二维码核验通过"}