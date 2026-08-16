# -*- coding: utf-8 -*-
"""InsightFace 人脸引擎（懒加载单例，兼容旧库 512 维模板）"""
import base64
import threading

import cv2
import numpy as np

_engine = None
_lock = threading.Lock()


def get_engine():
    """线程安全懒加载 buffalo_l 人脸分析引擎（首次调用时下载约 280MB 模型）"""
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                from insightface.app import FaceAnalysis

                print("正在加载人脸模型（首次运行会自动下载约280MB）")
                app = FaceAnalysis(
                    name="buffalo_l", providers=["CPUExecutionProvider"]
                )
                app.prepare(ctx_id=0, det_size=(640, 640))
                _engine = FaceEngine(app)
    return _engine


class FaceEngine:
    """人脸检测 / 512 维特征提取 / 相似度比对 / 简化静默活体"""

    def __init__(self, app=None):
        self.app = app

    # ---------- 检测与嵌入 ----------

    def detect_b64(self, image_b64: str) -> dict:
        """base64 图片 → {"faces": [face对象], "bgr": ndarray}

        兼容前端 canvas.toDataURL() 的 "data:image/xxx;base64," 前缀（自动剥离）；
        解码失败或 0 人脸时返回 {"faces": [], "bgr": None}
        """
        try:
            if image_b64.startswith("data:"):
                image_b64 = image_b64.split(",", 1)[-1]
            buf = np.frombuffer(base64.b64decode(image_b64), np.uint8)
            bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        except Exception:
            return {"faces": [], "bgr": None}
        if bgr is None:
            return {"faces": [], "bgr": None}
        faces = self.app.get(bgr)
        if not faces:
            return {"faces": [], "bgr": None}
        return {"faces": faces, "bgr": bgr}

    def embed(self, face) -> np.ndarray:
        """face.normed_embedding (512,) float32"""
        return np.asarray(face.normed_embedding, dtype=np.float32)

    def embed_b64_best(self, image_b64: str):
        """取检测到的最大面积人脸 → (embedding, face)；无人脸 → (None, None)"""
        faces = self.detect_b64(image_b64)["faces"]
        if not faces:
            return None, None
        best = self._largest(faces)
        return self.embed(best), best

    @staticmethod
    def _largest(faces):
        """按 bbox 面积取最大人脸"""
        return max(
            faces,
            key=lambda f: float((f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])),
        )

    # ---------- 相似度与模板 ----------

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> float:
        """两向量余弦相似度"""
        a = np.asarray(a, dtype=np.float32).ravel()
        b = np.asarray(b, dtype=np.float32).ravel()
        denom = float(np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0.0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def compare_with_template(self, template_bytes: bytes, embedding: np.ndarray) -> float:
        """旧库 blob(bytes, 512维 float32) 与当前 embedding 的余弦相似度"""
        if not template_bytes or embedding is None:
            return 0.0
        template = np.frombuffer(template_bytes, dtype=np.float32)
        return self.cosine(template, embedding)

    def embedding_to_bytes(self, embedding: np.ndarray) -> bytes:
        """float32 .tobytes()，用于存库（512 维 → 2048 字节）"""
        return np.asarray(embedding, dtype=np.float32).tobytes()

    # ---------- 简化静默活体 ----------

    def liveness_two_frames(self, b64_1: str, b64_2: str) -> dict:
        """两帧比对：关键点(kps, shape=(5,2))平均位移与 bbox 平均位移，

        任一超过 1.5px 判定存在活体动作；任一帧无人脸 → passed False。
        """
        faces_1 = self.detect_b64(b64_1)["faces"]
        if not faces_1:
            return {"passed": False, "reason": "第一帧未检测到人脸"}
        faces_2 = self.detect_b64(b64_2)["faces"]
        if not faces_2:
            return {"passed": False, "reason": "第二帧未检测到人脸"}

        f1, f2 = self._largest(faces_1), self._largest(faces_2)
        kps1, kps2 = getattr(f1, "kps", None), getattr(f2, "kps", None)
        if kps1 is None or kps2 is None:
            return {"passed": False, "reason": "关键点缺失，无法进行活体判定"}
        kps_shift = float(np.mean(np.linalg.norm(kps2 - kps1, axis=1)))
        bbox_shift = float(np.mean(np.abs(f2.bbox - f1.bbox)))
        if max(kps_shift, bbox_shift) > 1.5:
            return {"passed": True, "reason": "检测到活体动作"}
        return {"passed": False, "reason": "两帧几乎无变化，疑似照片"}
