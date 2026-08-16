# -*- coding: utf-8 -*-
"""演示种子数据（幂等）：可重复执行，绝不改动已有人员数据

- admin：upsert（admin / admin123）
- schedule：表为空时每门课补 2 条课表
- 演示作业 A/B：homework 无"演示"标题时创建（含测试用例）
- 历史业务数据：attendance_record 总数 < 30 时补考勤/互动/AI问答
- GradeBook 历史成绩：为演示作业 A 的选课学生补提交与成绩（逐条查重）
"""
import datetime
import itertools
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.geofence import DEFAULT_COORD
from app.core.judge.service import rule_feedback
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import (
    Admin,
    AiQaRecord,
    AttendanceRecord,
    ClassroomInteraction,
    Course,
    Enrollment,
    GradeBook,
    Homework,
    Schedule,
    Student,
    SubmissionRecord,
    TestCase,
)

random.seed(20260814)  # 固定随机种子：重复运行结果可复现

DEMO_CODE_SUM = "a, b = map(int, input().split())\nprint(a + b)\n"


def seed_admin(db) -> None:
    admin = db.query(Admin).filter(Admin.admin_no == "admin").first()
    if admin is None:
        db.add(
            Admin(
                admin_no="admin",
                name="系统管理员",
                password=hash_password("admin123"),
            )
        )
        print("[OK]   admin 已创建（admin / admin123）")
    else:
        # upsert：名称与密码始终对齐演示口径（幂等）
        admin.name = "系统管理员"
        admin.password = hash_password("admin123")
        print("[OK]   admin 已存在，密码已按演示口径重置")
    db.commit()


def seed_schedule(db) -> None:
    if db.query(Schedule).count() > 0:
        print("[SKIP] schedule 已有数据，不重复创建")
        return
    rows = [
        # CS101：周一 1-2 节 + 周三 3-4 节（CLS001）
        ("CS101", "CLS001", 1, "08:00", "09:40", "教A-301"),
        ("CS101", "CLS001", 3, "10:00", "11:40", "教A-301"),
        # CS102：周二上下午各一次（CLS001）
        ("CS102", "CLS001", 2, "08:00", "09:40", "教B-202"),
        ("CS102", "CLS001", 2, "14:00", "15:40", "教B-202"),
        # CS103：周四上下午各一次（CLS002）
        ("CS103", "CLS002", 4, "08:00", "09:40", "教C-105"),
        ("CS103", "CLS002", 4, "14:00", "15:40", "教C-105"),
    ]

    def _to_time(s: str) -> datetime.time:
        h, m = (int(x) for x in s.split(":"))
        return datetime.time(h, m)

    for course_id, class_id, weekday, start, end, classroom in rows:
        db.add(
            Schedule(
                course_id=course_id,
                class_id=class_id,
                weekday=weekday,
                start_time=_to_time(start),
                end_time=_to_time(end),
                weeks="1-16",
                classroom=classroom,
            )
        )
    db.commit()
    print(f"[OK]   schedule 已创建 {len(rows)} 条（每门课 2 条）")


def seed_demo_homework(db) -> list:
    """创建演示作业 A/B；返回演示作业 A 的 Homework 对象"""
    hw_a = db.query(Homework).filter(Homework.title.like("%演示作业A%")).first()
    if hw_a is not None:
        print("[SKIP] 演示作业已存在，不重复创建")
        return hw_a

    now = datetime.datetime.now()
    hw_a = Homework(
        course_id="CS101",
        teacher_id="T001",
        title="演示作业A：两数之和",
        description="输入两个整数（空格分隔），输出它们的和。\n"
        "示例：输入 `1 2`，输出 `3`。",
        programming_language="python",
        max_score=100,
        deadline=now + datetime.timedelta(days=7),
        status=1,
        feedback_visible=1,  # 教师已提前开放 AI 反馈，便于演示立即查看
    )
    hw_b = Homework(
        course_id="CS101",
        teacher_id="T001",
        title="演示作业B：字符串反转",
        description="输入一个字符串，输出其反转结果。\n示例：输入 `abc`，输出 `cba`。",
        programming_language="python",
        max_score=100,
        deadline=now + datetime.timedelta(days=14),
        status=1,
        feedback_visible=1,
    )
    db.add_all([hw_a, hw_b])
    db.commit()
    db.refresh(hw_a)
    db.refresh(hw_b)

    for hw, cases in (
        (
            hw_a,
            [
                ("用例1：正数", "1 2", "3", 0.3, True),
                ("用例2：负数", "-1 5", "4", 0.3, True),
                ("用例3：大数（隐藏）", "100 200", "300", 0.4, False),
            ],
        ),
        (
            hw_b,
            [
                ("用例1：短串", "abc", "cba", 0.5, True),
                ("用例2：常见词（隐藏）", "hello", "olleh", 0.5, False),
            ],
        ),
    ):
        for order, (name, tin, tout, weight, public) in enumerate(cases):
            db.add(
                TestCase(
                    homework_id=hw.id,
                    name=name,
                    test_input=tin,
                    expected_output=tout,
                    score_weight=weight,
                    is_public=1 if public else 0,
                    order_num=order,
                )
            )
    db.commit()
    print(f"[OK]   演示作业已创建：A(id={hw_a.id}) 两数之和 / B(id={hw_b.id}) 字符串反转")
    return hw_a


def _enrolled_students(db, course_id: str) -> list:
    return [
        sno
        for (sno,) in db.query(Student.student_no)
        .join(
            Enrollment,
            (Enrollment.student_id == Student.student_no)
            & (Enrollment.course_id == course_id)
            & (Enrollment.status == 1),
        )
        .order_by(Student.student_no)
        .all()
    ]


def seed_history(db) -> None:
    """历史业务数据：仅在 attendance_record 总数 < 30 时生成"""
    total_att = db.query(AttendanceRecord).count()
    if total_att >= 30:
        print(f"[SKIP] 历史业务数据（attendance_record 已有 {total_att} 条 ≥ 30）")
        return

    today = datetime.date.today()
    lat0, lng0 = DEFAULT_COORD

    # 1) 过去 14 天考勤：82% 出勤 / 8% 迟到 / 10% 缺勤，每课每生每天最多 1 条
    created = 0
    courses = [c.course_code for c in db.query(Course).order_by(Course.course_code).all()]
    for offset in range(14, 0, -1):
        day = today - datetime.timedelta(days=offset)
        for course_id in courses:
            for sno in _enrolled_students(db, course_id):
                exists = (
                    db.query(AttendanceRecord.id)
                    .filter(
                        AttendanceRecord.course_id == course_id,
                        AttendanceRecord.student_id == sno,
                        AttendanceRecord.attendance_date == day,
                    )
                    .first()
                )
                if exists:
                    continue
                status = random.choices([1, 2, 0], weights=[82, 8, 10])[0]
                lat = round(lat0 + random.uniform(-0.0008, 0.0008), 6)
                lng = round(lng0 + random.uniform(-0.0008, 0.0008), 6)
                db.add(
                    AttendanceRecord(
                        course_id=course_id,
                        student_id=sno,
                        attendance_date=day,
                        status=status,
                        check_in_time=(
                            datetime.datetime.combine(day, datetime.time(8, random.randint(0, 25)))
                            if status
                            else None
                        ),
                        check_in_type=1,
                        location=f"{lat},{lng}",
                        session_id=None,
                    )
                )
                created += 1
    db.commit()
    print(f"[OK]   历史考勤已生成 {created} 条（过去 14 天，82/8/10 分布）")

    # 2) 课堂互动 12 条（question/rating 混合）
    contents_q = ["回答积极", "思路清晰", "提出好问题", "主动上台演示"]
    contents_r = ["回答积极", "思路清晰"]
    for i in range(12):
        course_id = courses[i % len(courses)]
        students = _enrolled_students(db, course_id)
        if not students:
            continue
        is_q = i % 2 == 0
        db.add(
            ClassroomInteraction(
                course_id=course_id,
                student_id=random.choice(students),
                interaction_type="question" if is_q else "rating",
                content=contents_q[i % len(contents_q)] if is_q else contents_r[i % len(contents_r)],
                score=None if is_q else random.randint(3, 5),
                teacher_id="T001" if course_id != "CS103" else "T002",
                lesson_date=today - datetime.timedelta(days=random.randint(1, 14)),
            )
        )
    db.commit()
    print("[OK]   课堂互动已生成 12 条")

    # 3) AI 问答 2 条
    for q, a, anon in (
        ("python 怎么读入两个数？", "用 `a, b = map(int, input().split())`：input() 读整行，split() 按空格切分，map 逐个转 int。", 0),
        ("列表和元组区别？", "列表可变（list，支持增删改），元组不可变（tuple，创建后不能修改）；元组可作为字典键且开销更小。", 1),
    ):
        db.add(
            AiQaRecord(
                course_id="CS101",
                student_id="2024001",
                question=q,
                answer=a,
                is_anonymous=anon,
            )
        )
    db.commit()
    print("[OK]   AI 问答已生成 2 条")


def seed_demo_enrollment(db) -> None:
    """演示学生 2024004 当前无任何选课，为其补选 CS101（仅新增选课关系，
    不改动任何人员数据；幂等）"""
    sno = "2024004"
    if db.query(Enrollment.id).filter(
        Enrollment.course_id == "CS101", Enrollment.student_id == sno
    ).first():
        print("[SKIP] 2024004 已选 CS101")
        return
    if db.query(Student.student_no).filter(Student.student_no == sno).first() is None:
        print("[SKIP] 学生 2024004 不存在，跳过补选")
        return
    db.add(Enrollment(course_id="CS101", student_id=sno, status=1))
    db.commit()
    print("[OK]   已为 2024004 补选 CS101（原无任何选课，仅新增选课关系）")


def seed_gradebook(db, hw_a: Homework) -> None:
    """为演示作业 A 的选课学生生成历史提交 + 成绩（逐条查重，幂等）"""
    if hw_a is None:
        print("[SKIP] 演示作业 A 不存在，跳过历史成绩")
        return
    students = _enrolled_students(db, hw_a.course_id)
    if not students:
        print("[SKIP] 演示作业 A 无选课学生，跳过历史成绩")
        return
    cases = (
        db.query(TestCase)
        .filter(TestCase.homework_id == hw_a.id)
        .order_by(TestCase.order_num, TestCase.id)
        .all()
    )

    # 可达分数组合（权重和 0.6~1.0 → 得分 60~100）
    combos = []
    for r in range(1, len(cases) + 1):
        for combo in itertools.combinations(cases, r):
            w = sum(float(c.score_weight or 0) for c in combo)
            if 0.6 - 1e-9 <= w <= 1.0 + 1e-9:
                combos.append(combo)

    now = datetime.datetime.now()
    created = 0
    for sno in students:
        if (
            db.query(GradeBook.id)
            .filter(
                GradeBook.homework_id == hw_a.id, GradeBook.student_id == sno
            )
            .first()
        ):
            continue
        passed_cases = random.choice(combos)
        score = round(100 * sum(float(c.score_weight or 0) for c in passed_cases), 2)
        results = [
            {
                "case_id": c.id,
                "name": c.name,
                "passed": c in passed_cases,
                "stdout": (c.expected_output or "") if c in passed_cases else "",
                "expected": c.expected_output or "",
                "stderr": "",
                "time_ms": random.randint(8, 60),
                "is_public": bool(c.is_public),
            }
            for c in cases
        ]
        judge_time = now - datetime.timedelta(days=random.randint(1, 5))
        db.add(
            SubmissionRecord(
                homework_id=hw_a.id,
                student_id=sno,
                course_id=hw_a.course_id,
                submitted_code=DEMO_CODE_SUM,
                submit_time=judge_time - datetime.timedelta(hours=1),
                status=2,
                score=score,
                test_results=json.dumps(results, ensure_ascii=False),
                ai_feedback=rule_feedback(results, score),
                judge_time=judge_time,
            )
        )
        db.add(
            GradeBook(
                course_id=hw_a.course_id,
                homework_id=hw_a.id,
                student_id=sno,
                score=score,
                submit_count=random.randint(1, 3),
                judge_time=judge_time,
                create_time=judge_time,
                update_time=judge_time,
            )
        )
        created += 1
    db.commit()
    print(f"[OK]   演示作业 A 历史成绩已生成 {created} 条（学生 {students}）")


def print_summary() -> None:
    line = "=" * 62
    print(f"""
{line}
  演示数据就绪！四端入口（默认 http://127.0.0.1:8000）：
    门户/登录页   http://127.0.0.1:8000/index.html
    学生端        http://127.0.0.1:8000/student.html
    教师端        http://127.0.0.1:8000/teacher.html
    辅导员端      http://127.0.0.1:8000/counselor.html
    管理端        http://127.0.0.1:8000/admin.html
{line}
  演示账号（密码均为演示默认值）：
    管理员   admin / admin123
    教师     T001 / 123456   T002 / 123456
    辅导员   C001 / 123456   C002 / 123456
    学生     2024001 / 123456   2024002 / 123456
             2024003 / 123456   2024004 / 123456
             2451200817 / 123456
{line}
  人脸说明：
    - 2451200817（霍旭晖）已有人脸模板，可直接发起/参与人脸签到
    - 其余学生首次使用需在学生端"人脸注册"页面上传本人照片
{line}""")


def main() -> None:
    print("=" * 62)
    print("  开始写入演示种子数据（幂等，人员数据不受影响）")
    print("=" * 62)
    db = SessionLocal()
    try:
        seed_admin(db)
        seed_schedule(db)
        hw_a = seed_demo_homework(db)
        seed_demo_enrollment(db)
        seed_history(db)
        seed_gradebook(db, hw_a)
    finally:
        db.close()
    print_summary()


if __name__ == "__main__":
    main()
