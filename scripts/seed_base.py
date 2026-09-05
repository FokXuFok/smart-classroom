# -*- coding: utf-8 -*-
"""基础演示数据（幂等）：教师 / 辅导员 / 班级 / 课程 / 学生 / 辅导员管班 / 选课

为 seed_demo.py 提供 schedule / homework / enrollment / history / gradebook
等所需的基础外键数据，避免全新数据库种子时 IntegrityError：

  - 教师 T001 / T002
  - 辅导员 C001 / C002
  - 班级 CLS001 / CLS002
  - 课程 CS101 / CS102 / CS103
  - 学生 2024001~2024004 + 2451200817（霍旭晖，已有人脸模板）
  - 辅导员管班 C001-CLS001 / C002-CLS002
  - 选课：CLS001 学生 → CS101 / CS102（CLS002 暂无学生，CS103 课表仍可建）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password
from app.models import (
    ClassInfo,
    Course,
    Counselor,
    CounselorClass,
    Enrollment,
    Student,
    Teacher,
)


def seed_base(db) -> None:
    """幂等写入基础演示数据：教师 / 辅导员 / 班级 / 课程 / 学生 / 管班 / 选课

    每个实体先按主键查重，存在则跳过，不存在才创建；可重复执行不报错。
    """
    # ---- 教师 ----
    teachers = [
        ("T001", "张老师", 1, "计算机学院", "副教授"),
        ("T002", "李老师", 0, "计算机学院", "讲师"),
    ]
    t_created = 0
    for teacher_no, name, gender, department, title in teachers:
        if (
            db.query(Teacher.teacher_no)
            .filter(Teacher.teacher_no == teacher_no)
            .first()
        ):
            continue
        db.add(
            Teacher(
                teacher_no=teacher_no,
                name=name,
                gender=gender,
                department=department,
                title=title,
                password=hash_password("123456"),
                status=1,
            )
        )
        t_created += 1
    print(f"[OK]   teacher 已创建 {t_created} 条（T001/T002，密码 123456）")

    # ---- 辅导员 ----
    counselors = [
        ("C001", "王辅导员", 0, "计算机学院"),
        ("C002", "刘辅导员", 1, "计算机学院"),
    ]
    c_created = 0
    for counselor_no, name, gender, department in counselors:
        if (
            db.query(Counselor.counselor_no)
            .filter(Counselor.counselor_no == counselor_no)
            .first()
        ):
            continue
        db.add(
            Counselor(
                counselor_no=counselor_no,
                name=name,
                gender=gender,
                department=department,
                password=hash_password("123456"),
                status=1,
            )
        )
        c_created += 1
    print(f"[OK]   counselor 已创建 {c_created} 条（C001/C002，密码 123456）")

    # ---- 班级 ----
    classes = [
        ("CLS001", "计算机2024-1班", "2024", "计算机科学与技术", "计算机学院", 5),
        ("CLS002", "计算机2024-2班", "2024", "计算机科学与技术", "计算机学院", 0),
    ]
    cls_created = 0
    for class_code, class_name, grade, major, department, student_count in classes:
        if (
            db.query(ClassInfo.class_code)
            .filter(ClassInfo.class_code == class_code)
            .first()
        ):
            continue
        db.add(
            ClassInfo(
                class_code=class_code,
                class_name=class_name,
                grade=grade,
                major=major,
                department=department,
                student_count=student_count,
            )
        )
        cls_created += 1
    print(f"[OK]   class 已创建 {cls_created} 条（CLS001/CLS002）")

    # 先提交一次：teacher/counselor/class 已落库，后续 course/student 外键才能找到
    db.commit()

    # ---- 课程（FK → teacher.teacher_no）----
    courses = [
        ("CS101", "数据结构", 3, 48, "2024-2025-1", "T001"),
        ("CS102", "算法设计", 3, 48, "2024-2025-1", "T001"),
        ("CS103", "操作系统", 3, 64, "2024-2025-1", "T002"),
    ]
    cs_created = 0
    for course_code, course_name, credit, hours, semester, teacher_id in courses:
        if (
            db.query(Course.course_code)
            .filter(Course.course_code == course_code)
            .first()
        ):
            continue
        db.add(
            Course(
                course_code=course_code,
                course_name=course_name,
                credit=credit,
                hours=hours,
                semester=semester,
                teacher_id=teacher_id,
                status=1,
            )
        )
        cs_created += 1
    print(f"[OK]   course 已创建 {cs_created} 条（CS101/CS102/CS103）")

    # ---- 学生（class_id NOT NULL，逻辑外键 → class.class_code）----
    # 2451200817（霍旭晖）已有人脸模板，但人脸模板由其它机制维护，此处仅建 student 记录
    students = [
        ("2024001", "陈思远", 1, "CLS001"),
        ("2024002", "林雨欣", 0, "CLS001"),
        ("2024003", "赵明", 1, "CLS001"),
        ("2024004", "周婷", 0, "CLS001"),
        ("2451200817", "霍旭晖", 1, "CLS001"),
    ]
    s_created = 0
    for student_no, name, gender, class_id in students:
        if (
            db.query(Student.student_no)
            .filter(Student.student_no == student_no)
            .first()
        ):
            continue
        db.add(
            Student(
                student_no=student_no,
                name=name,
                gender=gender,
                password=hash_password("123456"),
                status=1,
                class_id=class_id,
            )
        )
        s_created += 1
    print(
        f"[OK]   student 已创建 {s_created} 条"
        "（2024001~2024004 + 2451200817，密码 123456）"
    )

    # 先提交一次：确保后续 CounselorClass / Enrollment 的外键行已落库
    db.commit()

    # ---- 辅导员管班（复合 PK: counselor_id + class_id）----
    cc_rows = [("C001", "CLS001"), ("C002", "CLS002")]
    cc_created = 0
    for counselor_id, class_id in cc_rows:
        if (
            db.query(CounselorClass.class_id)
            .filter(
                CounselorClass.counselor_id == counselor_id,
                CounselorClass.class_id == class_id,
            )
            .first()
        ):
            continue
        db.add(CounselorClass(counselor_id=counselor_id, class_id=class_id))
        cc_created += 1
    print(
        f"[OK]   counselor_class 已创建 {cc_created} 条"
        "（C001-CLS001 / C002-CLS002）"
    )

    # ---- 选课（UK: course_id + student_id）----
    # CLS001 学生 → CS101 / CS102；CLS002 暂无学生，CS103 课表仍可建（无选课关系）
    cls001_students = [s[0] for s in students if s[3] == "CLS001"]
    enrollment_rows = []
    for sno in cls001_students:
        enrollment_rows.append((sno, "CS101"))
        enrollment_rows.append((sno, "CS102"))
    e_created = 0
    for student_id, course_id in enrollment_rows:
        if (
            db.query(Enrollment.id)
            .filter(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
            )
            .first()
        ):
            continue
        db.add(Enrollment(student_id=student_id, course_id=course_id, status=1))
        e_created += 1
    print(
        f"[OK]   enrollment 已创建 {e_created} 条"
        "（CLS001 学生选 CS101/CS102）"
    )

    db.commit()
    print("[OK]   seed_base 完成（基础演示数据已就绪）")


if __name__ == "__main__":
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        seed_base(db)
    finally:
        db.close()
