# -*- coding: utf-8 -*-
"""密码哈希与 JWT"""
import datetime

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
    """签发 JWT：sub=工号/学号，role，name，instance_id，exp=now+TOKEN_EXPIRE_HOURS"""
    payload = {
        "sub": user_id,
        "role": role,
        "name": name,
        "instance_id": instance_id,
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=config.TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """解码并校验 JWT；过期抛 jwt.ExpiredSignatureError，非法抛 jwt.InvalidTokenError"""
    return jwt.decode(token, config.SECRET_KEY, algorithms=["HS256"])
