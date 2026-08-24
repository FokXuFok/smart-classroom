# -*- coding: utf-8 -*-
"""密码哈希与 JWT"""
import datetime
import threading
import uuid

import bcrypt
import jwt

import config


def hash_password(plain: str) -> str:
    """bcrypt 哈希，返回 utf-8 str"""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码；兼容旧库哈希；hashed 非法时返回 False 而非抛错"""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        # 旧库遗留明文/MD5/截断等非法 bcrypt 哈希：直接判定不匹配
        return False


def create_token(user_id: str, role: str, name: str, instance_id: str = "") -> str:
    """签发 JWT：sub=工号/学号，role，name，instance_id，jti，exp=now+TOKEN_EXPIRE_HOURS"""
    payload = {
        "sub": user_id,
        "role": role,
        "name": name,
        "instance_id": instance_id,
        "jti": uuid.uuid4().hex,  # token 唯一编号，登出时加入黑名单
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=config.TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """解码并校验 JWT；过期抛 jwt.ExpiredSignatureError，非法抛 jwt.InvalidTokenError"""
    return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])


# ---- 登出黑名单（内存版）----
# jti -> exp(Unix秒)。登出后的 token 在过期前一律拒绝。
# 单体单进程演示口径：重启服务黑名单清空，但同时 instance_id 也会变化，
# 旧 token 依然全部失效，故重启不产生安全缺口；多进程/生产需换 Redis。
_revoked: dict = {}
_revoked_lock = threading.Lock()
# 清理阈值：条目数超过该值时顺手剔除已过期条目
_CLEANUP_THRESHOLD = 4096


def revoke_token(jti: str, exp: int) -> None:
    """把指定 token 加入黑名单（exp 为该 token 的过期时间戳）"""
    if not jti or not exp:
        return
    with _revoked_lock:
        _revoked[jti] = int(exp)
        if len(_revoked) > _CLEANUP_THRESHOLD:
            now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
            for dead in [k for k, v in _revoked.items() if v <= now]:
                del _revoked[dead]


def is_token_revoked(jti: str) -> bool:
    """token 是否已登出作废（顺手剔除已过期黑名单条目，避免内存增长）"""
    if not jti:
        return False
    exp = _revoked.get(jti)
    if exp is None:
        return False
    if exp <= datetime.datetime.now(datetime.timezone.utc).timestamp():
        with _revoked_lock:
            _revoked.pop(jti, None)
        return False
    return True
