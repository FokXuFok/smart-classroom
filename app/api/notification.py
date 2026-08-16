# -*- coding: utf-8 -*-
"""通知服务：站内消息推送 helper（供其他模块调用）+ 查询 / 已读接口"""
from fastapi import APIRouter, Depends
from sqlalchemy import func

from app.api.deps import CurrentUser, get_current_user, get_db
from app.core.exception import BizError, ok
from app.models import Notification

router = APIRouter(prefix="/api/notification", tags=["notification"])

# role → 各表主键字段（用于把编号转成 notification.user_id bigint）
ROLE_PK = {
    "student": "student_no",
    "teacher": "teacher_no",
    "counselor": "counselor_no",
    "admin": "admin_no",
}


def push(
    db,
    user_no,
    user_type: str,
    notif_type: str,
    title: str,
    content: str,
    related_id=None,
    course_id=None,
) -> None:
    """写一条通知（独立提交，任何异常静默回滚，绝不影响主流程）。

    notification.user_id 是 bigint：学生学号是字符串数字，int() 转换；
    非数字编号（如 T001 / C001）直接跳过。
    """
    try:
        uid = int(user_no)
    except (TypeError, ValueError):
        return
    try:
        db.add(
            Notification(
                user_id=uid,
                user_type=user_type,
                notif_type=notif_type,
                title=(title or "")[:200],
                content=content,
                related_id=related_id,
                course_id=course_id,
                is_read=0,
            )
        )
        db.commit()
    except Exception:
        db.rollback()


def _my_uid(current: CurrentUser):
    """当前用户编号 → bigint；非数字返回 None（不可能有通知）"""
    pk = ROLE_PK.get(current.role)
    if pk is None:
        return None
    try:
        return int(getattr(current.user, pk))
    except (TypeError, ValueError):
        return None


def _notif_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "notif_type": n.notif_type,
        "title": n.title,
        "content": n.content,
        "related_id": n.related_id,
        "course_id": n.course_id,
        "is_read": n.is_read,
        "create_time": n.create_time,
    }


@router.get("/list")
def list_notifications(
    limit: int = 20,
    current: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
):
    uid = _my_uid(current)
    if uid is None:
        return ok({"unread_count": 0, "items": []})
    limit = max(1, min(limit, 100))
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == uid,
            Notification.user_type == current.role,
            Notification.is_read == 0,
        )
        .scalar()
    )
    rows = (
        db.query(Notification)
        .filter(
            Notification.user_id == uid,
            Notification.user_type == current.role,
        )
        .order_by(Notification.id.desc())
        .limit(limit)
        .all()
    )
    return ok(
        {"unread_count": unread_count or 0, "items": [_notif_dict(n) for n in rows]}
    )


@router.post("/read/{notif_id}")
def read_notification(
    notif_id: int,
    current: CurrentUser = Depends(get_current_user),
    db=Depends(get_db),
):
    uid = _my_uid(current)
    n = db.query(Notification).filter(Notification.id == notif_id).first()
    if n is None:
        raise BizError(404, "通知不存在")
    if uid is None or n.user_id != uid or n.user_type != current.role:
        raise BizError(403, "无权限操作该通知")
    if not n.is_read:
        n.is_read = 1
        db.commit()
    return ok({"id": notif_id, "is_read": 1}, message="已标记为已读")


@router.post("/read-all")
def read_all(current: CurrentUser = Depends(get_current_user), db=Depends(get_db)):
    uid = _my_uid(current)
    if uid is None:
        return ok({"updated": 0}, message="全部已读")
    updated = (
        db.query(Notification)
        .filter(
            Notification.user_id == uid,
            Notification.user_type == current.role,
            Notification.is_read == 0,
        )
        .update({"is_read": 1}, synchronize_session=False)
    )
    db.commit()
    return ok({"updated": updated}, message="全部已读")
