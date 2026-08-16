# -*- coding: utf-8 -*-
"""数据库增量升级（幂等）：只新建缺失的表/约束/视图，绝不删改已有数据"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from app.database import Base, engine
from app.models import *  # noqa: F401,F403  导入即注册全部 ORM 模型

# 可安全忽略的 MySQL errno（对象已存在类错误）：
# 1050 表已存在 / 1060 字段已存在 / 1061 索引(键名)已存在 / 1826 外键约束名已存在
# 注意：不忽略 1005/1091 等非"已存在"错误，避免吞掉真实失败
IGNORABLE_ERRNOS = {1050, 1060, 1061, 1826}

FK_ATT_SESSION_SQL = (
    "ALTER TABLE attendance_record ADD CONSTRAINT fk_att_session "
    "FOREIGN KEY(session_id) REFERENCES checkin_session(id)"
)

VIEW_SQL = """CREATE OR REPLACE VIEW v_student_attendance AS
SELECT ar.id, ar.course_id, ar.student_id, s.name AS student_name, ar.attendance_date, ar.status,
       ar.check_in_time, ar.check_in_type, c.course_name
FROM attendance_record ar JOIN student s ON ar.student_id=s.student_no
JOIN course c ON ar.course_id=c.course_code"""


def _list_tables() -> set:
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(text("SHOW TABLES"))}


def _run_patch(desc: str, sql: str) -> None:
    """执行单条增量补丁 DDL，对象已存在时安全跳过"""
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        print(f"[OK]   {desc}")
    except (OperationalError, ProgrammingError) as e:
        errno = getattr(getattr(e, "orig", None), "args", [None])[0]
        if errno in IGNORABLE_ERRNOS:
            print(f"[SKIP] {desc}（已存在，errno={errno}）")
        else:
            raise
    except IntegrityError as e:
        errno = getattr(getattr(e, "orig", None), "args", [None])[0]
        if errno == 1452:
            # 存量历史数据与新约束冲突：绝不删改已有数据，仅警告并跳过
            print(f"[WARN] {desc}（errno=1452：存量数据存在悬空引用，"
                  f"为不改动已有数据已跳过，待数据治理后重跑即可生效）")
        else:
            raise


def main() -> None:
    # 1. 导入 app.models 已在模块顶部完成，全部表已注册到 Base.metadata

    # 2. 只新建缺失的表（checkfirst=True：已有表原样保留，不重建不改结构）
    before = _list_tables()
    Base.metadata.create_all(engine, checkfirst=True)
    after = _list_tables()
    created = sorted(after - before)
    print(f"[OK]   create_all 完成，本次新建表: {created if created else '无（均已存在）'}")

    # 3. 增量补丁：缺失外键 + 并发防重唯一约束 + 重建视图（均可重复执行）
    _run_patch("为 attendance_record.session_id 补外键 fk_att_session", FK_ATT_SESSION_SQL)
    _run_patch(
        "为 attendance_record 补唯一约束 uk_session_student（防并发重复签到）",
        "ALTER TABLE attendance_record ADD UNIQUE KEY uk_session_student (session_id, student_id)",
    )
    _run_patch("重建视图 v_student_attendance", VIEW_SQL)
    _run_patch(
        "为 notification 补联合索引 idx_user_type_is_read（未读通知筛选）",
        "ALTER TABLE notification ADD INDEX idx_user_type_is_read (user_id, user_type, is_read)",
    )

    # 4. 结果摘要
    print(f"[DONE] 增量升级完成：库中共 {len(after)} 个表/视图（含视图）")


if __name__ == "__main__":
    main()
