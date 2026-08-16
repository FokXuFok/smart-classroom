# -*- coding: utf-8 -*-
"""人脸引擎测试：向量工具无需模型；检测/活体管线依赖 buffalo_l（就绪才执行）"""
from base64 import b64encode
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.face_engine import FaceEngine, get_engine

MODEL_DIR = Path.home() / ".insightface" / "models" / "buffalo_l"
MODEL_READY = MODEL_DIR.is_dir() and len(list(MODEL_DIR.glob("*.onnx"))) == 5

requires_model = pytest.mark.skipif(not MODEL_READY, reason="buffalo_l 模型未就绪（下载中）")


def _b64_color_image(size: int = 300) -> str:
    """生成纯色图并编码为 base64 jpg"""
    img = np.full((size, size, 3), 128, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return b64encode(buf.tobytes()).decode()


class _FakeFace:
    """仅含 kps / bbox 的假 face 对象，用于无模型测试活体逻辑"""

    def __init__(self, kps, bbox):
        self.kps = np.array(kps, dtype=np.float32)
        self.bbox = np.array(bbox, dtype=np.float32)


# ---------- 向量工具（无需模型） ----------

def test_embedding_bytes_roundtrip():
    eng = FaceEngine(None)
    rng = np.random.default_rng(42)
    vec = rng.normal(size=512).astype(np.float32)
    vec /= np.linalg.norm(vec)

    blob = eng.embedding_to_bytes(vec)
    assert isinstance(blob, bytes)
    assert len(blob) == 512 * 4

    sim = eng.compare_with_template(blob, vec)
    assert abs(sim - 1.0) < 1e-5


def test_compare_different_random_vectors():
    eng = FaceEngine(None)
    rng = np.random.default_rng(42)
    a = rng.normal(size=512)
    a /= np.linalg.norm(a)
    b = rng.normal(size=512)
    b /= np.linalg.norm(b)

    assert abs(eng.compare_with_template(eng.embedding_to_bytes(a), b)) < 0.5


def test_cosine_manual():
    # 正交 → 0；同向 → 1
    assert abs(FaceEngine.cosine(np.array([1.0, 0.0]), np.array([0.0, 1.0]))) < 1e-9
    assert abs(FaceEngine.cosine(np.array([1.0, 0.0]), np.array([2.0, 0.0])) - 1.0) < 1e-9


def test_detect_b64_invalid_input():
    # 非法 base64 不崩，返回空结果
    assert FaceEngine(None).detect_b64("!!!不是base64!!!") == {"faces": [], "bgr": None}


def test_detect_b64_strips_data_uri_prefix(monkeypatch):
    # 前端 canvas.toDataURL() 必带 data: 前缀，必须自动剥离后再解码
    eng = FaceEngine(None)
    captured = {}

    def fake_get(bgr):
        return []

    class FakeApp:
        def get(self, bgr):
            captured["shape"] = bgr.shape
            return []

    eng.app = FakeApp()
    plain = _b64_color_image(300)
    eng.detect_b64("data:image/jpeg;base64," + plain)
    # 前缀被剥离 → imdecode 成功 → FakeApp.get 收到 300x300 图像
    assert captured.get("shape") == (300, 300, 3)


# ---------- 活体判定逻辑（假 face 对象，无需模型） ----------

def test_liveness_logic_with_fake_faces(monkeypatch):
    eng = FaceEngine(None)
    still = _FakeFace(
        [[10, 10], [20, 10], [15, 20], [12, 25], [18, 25]], [0, 0, 100, 100]
    )
    moved = _FakeFace(
        [[14, 11], [25, 9], [19, 24], [16, 29], [22, 29]], [3, 1, 104, 101]
    )

    monkeypatch.setattr(
        eng, "detect_b64", lambda _: {"faces": [still], "bgr": None}
    )
    assert eng.liveness_two_frames("f1", "f2") == {
        "passed": False,
        "reason": "两帧几乎无变化，疑似照片",
    }

    # 第一帧 still、第二帧 moved：关键点位移 4px > 1.5
    monkeypatch.setattr(
        eng,
        "detect_b64",
        lambda b64: {"faces": [still], "bgr": None} if b64 == "f1" else {"faces": [moved], "bgr": None},
    )
    result = eng.liveness_two_frames("f1", "f2")
    assert result["passed"] is True
    assert result["reason"] == "检测到活体动作"


def test_liveness_no_face(monkeypatch):
    eng = FaceEngine(None)
    monkeypatch.setattr(eng, "detect_b64", lambda _: {"faces": [], "bgr": None})
    result = eng.liveness_two_frames("f1", "f2")
    assert result["passed"] is False
    assert "未检测到人脸" in result["reason"]


# ---------- 真实模型管线（模型就绪才执行） ----------

@requires_model
def test_pipeline_no_face_on_plain_image():
    eng = get_engine()
    b64 = _b64_color_image(300)

    result = eng.detect_b64(b64)
    assert result == {"faces": [], "bgr": None}

    best = eng.embed_b64_best(b64)
    assert best == (None, None)
