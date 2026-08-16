# 全流程智慧课堂系统 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重建大创"全流程智慧课堂系统"后端（FastAPI+MySQL）+ 四端静态 HTML 前端，签到改为 人脸(InsightFace)+定位(200米)+指纹(预留接口)，main.py 一键启动。

**Architecture:** FastAPI 单体模块化（api/core/models/web 分层），沿用旧库 smart_classroom 增量升级（只加不删），InsightFace 本地 onnxruntime 推理（兼容旧 512 维模板），作业评测本地进程隔离沙箱（Docker Runner 预留），AI 走阿里百炼 OpenAI 兼容接口（deepseek-V4-pro，无 Key/失败自动降级规则引擎）。

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy 2.0, PyMySQL, bcrypt, PyJWT, insightface, opencv-python, onnxruntime, httpx, pytest；前端原生 HTML/JS/CSS（无构建）。

**已确认决策:**
- 数据库：沿用 `smart_classroom`（root/*** 密码存 .env***@localhost），增量升级补 `admin`/`schedule` 表；人员数据（5学生/2教师/2辅导员，bcrypt 密码）不动
- 人脸：InsightFace buffalo_l（512 维余弦相似度，阈值 0.40）；活体=两帧差检测（简化静默活体）
- 指纹：`core/fingerprint.py` 仅留接口 stub，签到请求可带 `fingerprint` 字段，返回 "not_enabled"
- 评测沙箱：`LocalProcessRunner`（临时目录+timeout+输出截断+Python import 黑名单；C/C++/Java 检测工具链缺失时返回可读错误）+ `DockerRunner` 预留接口
- AI：`base_url=https://dashscope.aliyuncs.com/compatible-mode/v1`，`model=deepseek-V4-pro`，Key 已由用户提供写入 config.py；任何失败→规则降级
- 前端：web/ 静态页（index 登录页按角色跳转 + student/teacher/counselor/admin 四端）
- main.py：检查依赖(缺则自动 pip install)→ init_db → (可选 --seed) → uvicorn → 自动开浏览器
- git：本地仓库，中文 commit

**目录结构:**
```
d:\大创（新）\
├── main.py  requirements.txt  config.py  .gitignore
├── app/
│   ├── __init__.py  database.py
│   ├── models/ (user, course, attendance, homework, interaction, system)  __init__.py 导出全部
│   ├── schemas/ (auth, checkin, homework, interaction, common)
│   ├── core/ (security, exception, face_engine, geofence, fingerprint, ai_client, judge/)
│   └── api/ (__init__ 汇总 router, deps, auth, student, teacher, counselor, admin, ai)
├── web/ (index.html, student.html, teacher.html, counselor.html, admin.html, css/style.css, js/api.js, js/common.js)
├── scripts/ (init_db.py, seed_demo.py)
├── tests/ (conftest.py, test_geofence.py, test_judge.py, test_security.py, test_score.py, test_api_smoke.py)
└── docs/superpowers/ (specs, plans)
```

**关键契约（全项目统一，勿改名）:**
- 统一响应: `{"code":0,"message":"ok","data":...}`，错误 `{"code":非0,"message":...}`；HTTP 始终 200（业务码区分）
- JWT payload: `{sub:"学号/工号", role:"student|teacher|counselor|admin", name, exp}`
- 登录: `POST /api/auth/login {username,password,role}` → `{token, role, name, user_id}`
- 签到: `POST /api/teacher/checkin/start {course_id,lat,lng,range_meters,duration_minutes}`；`GET /api/student/checkin/active`；`POST /api/student/checkin/submit {session_id,image_b64,lat,lng,fingerprint?}`（image_b64 不带 data: 前缀）；`GET /api/teacher/checkin/dashboard/{session_id}`；`POST /api/teacher/checkin/{id}/review`（补签审核）
- 人脸注册: `POST /api/student/face/register {image_b64}`（无模板或 face_regen_allowed=1 时允许）
- ORM 类名: Student/Teacher/Counselor/Admin/Course/Enrollment/ClassInfo/Schedule/CheckinSession/AttendanceRecord/Homework/TestCase/SubmissionRecord/GradeBook/CodeSimilarity/ClassroomInteraction/AiQaRecord/AiKnowledgeBase/AiScoringRule/AiCommonError/ErrorClassification/Notification/AuditLog/LoginAttempt
- 阈值(config.py): FACE_SIM_THRESHOLD=0.40, GEOFENCE_DEFAULT_M=200, LATE_MINUTES=10

---

### Task 1: 项目骨架

**Files:** Create `.gitignore`, `requirements.txt`, `config.py`, `app/__init__.py`, `app/database.py`, `tests/conftest.py`

- [ ] `git init` + `.gitignore`（`__pycache__/ *.pyc .pytest_cache/ models_cache/ *.onnx .env venv/`）
- [ ] `requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.29
sqlalchemy>=2.0
pymysql>=1.1
cryptography>=42
bcrypt>=4.1
PyJWT>=2.8
pydantic>=2.6
insightface>=0.7.3
opencv-python>=4.9
numpy>=1.24
onnxruntime>=1.17
httpx>=0.27
pytest>=8.0
```
- [ ] `config.py`（全部集中配置，含 AI Key——用户提供）:
```python
import os
from pathlib import Path
BASE_DIR = Path(__file__).parent
DB_URL = "mysql+pymysql://root:CHANGE_ME@localhost:3306/smart_classroom?charset=utf8mb4"
SECRET_KEY = "CHANGE_ME-please-set-in-.env"
TOKEN_EXPIRE_HOURS = 12
FACE_SIM_THRESHOLD = 0.40
GEOFENCE_DEFAULT_M = 200
LATE_MINUTES = 10
AI_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")  # 真实 Key 存 .env，不入库
AI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
AI_MODEL = "deepseek-V4-pro"
UPLOAD_DIR = BASE_DIR / "uploads"
```
- [ ] `app/database.py`: SQLAlchemy engine(URL from config, pool_pre_ping=True, pool_recycle=3600) + SessionLocal + get_db 生成器
- [ ] `tests/conftest.py`: 空 fixture 占位（后续任务扩充）
- [ ] Commit: `git init 项目骨架与配置`

### Task 2: ORM 模型层 + init_db

**Files:** Create `app/models/__init__.py`, `app/models/user.py`, `app/models/course.py`, `app/models/attendance.py`, `app/models/homework.py`, `app/models/interaction.py`, `app/models/system.py`, `scripts/init_db.py`

- [ ] 按旧库 DDL 逐字段映射（类型/默认值/外键与库一致，类名按"关键契约"，`ClassInfo.__tablename__="class"`，`face_template=Column(LargeBinary)`）
- [ ] 新表 `Admin`（admin_no PK, name, password bcrypt, status, create_time）与 `Schedule`（id PK AI, course_id FK, class_id, weekday 1-7, start_time time, end_time time, weeks varchar(50) 如"1-16", classroom varchar(100), UNIQUE(course_id,class_id,weekday,start_time)）
- [ ] `scripts/init_db.py`：`Base.metadata.create_all(engine, checkfirst=True)` 幂等——只为新表/新列生效；再执行两条补丁 DDL（try/except 忽略已存在）：`ALTER TABLE attendance_record ADD CONSTRAINT fk_att_schedule FOREIGN KEY(session_id) REFERENCES checkin_session(id)`；重建视图 v_student_attendance（CREATE OR REPLACE）。运行 `python scripts/init_db.py` 验证：无报错 + `SHOW TABLES` 出现 admin/schedule
- [ ] Commit: `feat: ORM模型层与数据库增量升级脚本`

### Task 3: 安全层 + 认证路由

**Files:** Create `app/core/__init__.py`, `app/core/exception.py`, `app/core/security.py`, `app/schemas/auth.py`, `app/api/__init__.py`, `app/api/deps.py`, `app/api/auth.py`, `tests/test_security.py`

- [ ] `exception.py`: `BizError(code,msg)` + FastAPI exception_handler → `{"code":code,"message":msg}`；统一成功包装函数 `ok(data=None)`
- [ ] `security.py`: `hash_password/verify_password`(bcrypt)、`create_token(payload)`(exp=now+TOKEN_EXPIRE_HOURS)、`decode_token(token)`
- [ ] `deps.py`: `get_current_user`(Authorization: Bearer，按 role 查对应表，返回 ORM 对象或抛 401 BizError；login_attempt 锁定逻辑：连续失败≥5 锁 10 分钟，用旧表 login_attempt)
- [ ] `api/auth.py`: `POST /api/auth/login` 按角色查表验密→token；`GET /api/auth/me`
- [ ] `test_security.py`: 密码哈希/校验、token 编解码过期、错误密码登录失败码。Run: `pytest tests/test_security.py -v` PASS
- [ ] Commit: `feat: JWT安全层与登录认证`

### Task 4: 核心引擎（人脸/围栏/指纹）

**Files:** Create `app/core/face_engine.py`, `app/core/geofence.py`, `app/core/fingerprint.py`, `tests/test_geofence.py`

- [ ] `face_engine.py`: 懒加载单例 `FaceEngine`（`FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])`，ctx_id=-1，prepare(ctx_id, det_size=(640,640))）；`detect(bgr_ndarray)->List[face]`；`embedding(face)->np.ndarray(512,) float32`；`compare(emb1_bytes, emb2: np.ndarray)->float`（归一化余弦）；`detect_from_b64(image_b64)`（np.frombuffer(base64.b64decode) → cv2.imdecode → BGR）。兼容旧库 blob（512×float32 直接 bytes→np）。首次初始化打印"正在下载/加载人脸模型（首次约 280MB）"
- [ ] `geofence.py`: `haversine_m(lat1,lng1,lat2,lng2)->float`（R=6371000），`within_range(teacher, student, range_m)->(bool, dist)`；桂林信息科技学院默认坐标 25.272,110.331 写入常量供种子/测试
- [ ] `fingerprint.py`: `verify(student_no, fingerprint_data)->{"enabled":False,"passed":None,"message":"指纹核验接口预留，未启用"}`（stub，注释注明未来接指纹设备）
- [ ] `test_geofence.py`: 同点距离≈0、200 米内 True、300 米 False、边界值。Run: `pytest tests/test_geofence.py -v` PASS
- [ ] Commit: `feat: 人脸/地理围栏引擎与指纹预留接口`

### Task 5: 签到模块 API

**Files:** Create `app/schemas/checkin.py`, `app/api/teacher.py`(签到部分), `app/api/student.py`(签到+人脸注册部分), tests 扩充

- [ ] 教师: `POST /api/teacher/checkin/start`（校验 course 属于该教师，写 checkin_session，status=1）；`POST /api/teacher/checkin/{session_id}/end`；`GET /api/teacher/checkin/dashboard/{session_id}`（返回选课名单+每生签到状态/相似度/距离/时间，未签=缺勤）；`POST /api/teacher/checkin/attendance/{id}/review` {action: approve/reject, remark}（补签审核→status 4→1 或维持）
- [ ] 学生: `GET /api/student/checkin/active`（本人选课的进行中会话+剩余分钟）；`POST /api/student/checkin/submit`——流程：会话有效→geofence(within range_meters)→face_engine.detect 单人脸→与本人 face_template 比对 ≥ FACE_SIM_THRESHOLD→fingerprint.verify(stub)→写 attendance_record（status: 会话开始≤LATE_MINUTES=1 正常否则 2 迟到；check_in_type=1；similarity1；location="lat,lng"；student_image_url 存 uploads/checkin/{student_no}_{ts}.jpg）；重复提交返回已签到。人脸失败→review_status=1 待人工复核+记录；无模板→提示先注册人脸。`GET /api/student/checkin/history?course_id=`；`POST /api/student/checkin/apply` {session_id, reason} 补签申请
- [ ] `POST /api/student/face/register {image_b64}`（无模板或 face_regen_allowed=1；成功后 face_regen_allowed 复位 0）；`PUT /api/teacher/student/{student_no}/face-regen` 授权
- [ ] 单测：签到判定（正常/迟到/超范围/相似度不足）用 mock face_engine。Run: `pytest -v` PASS
- [ ] Commit: `feat: 人脸+定位签到与补签审核`

### Task 6: 作业评测沙箱

**Files:** Create `app/core/judge/__init__.py`, `app/core/judge/runner.py`, `app/core/judge/similarity.py`, `app/schemas/homework.py`, `app/api/homework.py`, `tests/test_judge.py`, `tests/test_score.py`

- [ ] `runner.py`: `LocalProcessRunner.run(code, language, stdin, time_limit_ms)->{ok, stdout, stderr, time_ms}`；language∈python/c/cpp/java；python: 临时 main.py + `subprocess.run([sys.executable,"-I",...], timeout)`（`-I` 隔离站点）+ 源码 import 黑名单(os/system/subprocess/shutil/socket)；c/cpp/java: 探测 gcc/g++/javac（shutil.which），缺则 `{ok:False, stderr:"本机未安装 xxx 工具链"}`；输出截断 64KB。`DockerRunner` 类留构造+run 抛 NotImplemented，docstring 说明切换方式
- [ ] 评测流程 `judge_homework(submission)`：逐 test_case 运行→精确比对 stdout（strip 尾空白）→按 score_weight 加权求和→写 submission_record(status=1, score, test_results JSON, compile_error)→upsert grade_book（取最高分）→触发 AI 批改（Task7 接入，此处调 `ai_client.grade_feedback(...)` 空实现占位）。background_tasks 异步执行
- [ ] `similarity.py`: 简化 winnowing——去注释/空白→3-gram 集合 Jaccard；`check_homework_similarity(homework_id)` 汇总同作业全部最高分提交两两比对>0.8 写 code_similarity
- [ ] API: 教师 `POST /api/homework/`（含 test_case 数组）、`GET /api/homework/list?course_id=`、`GET /api/homework/{id}`、`PUT /api/homework/{id}`、`GET /api/homework/{id}/submissions`、`POST /api/homework/{id}/similarity`；学生 `GET /api/student/homework/list`、`GET /api/student/homework/{id}`（隐藏 is_public=0 用例的输入输出）、`POST /api/student/homework/{id}/submit {code, language}`（截止后 allow_late_submit=0 拒绝）、`GET /api/student/homework/{id}/my`（我的提交+反馈）
- [ ] `test_judge.py`: python "print(1+1)" stdin 空 → stdout "2"；超时用例；黑名单拦截；`test_score.py`: 权重计分 60*0.4+40*0.6=60。Run PASS
- [ ] Commit: `feat: 编程作业评测沙箱与成绩簿`

### Task 7: AI 模块（百炼 deepseek-V4-pro）

**Files:** Create `app/core/ai_client.py`, `app/api/ai.py`, 扩充 judge 流程接入

- [ ] `ai_client.py`: httpx.Client(timeout=60)；`chat(messages, temperature=0.3, max_tokens=2000)` POST {base_url}/chat/completions；**任何异常/无 Key→抛 AiUnavailable**；`grade_feedback(course, homework_title, language, code, test_results, scoring_rules)->str`：组装 system=学科 Agent（限定学科范围+踩分点评分+错误归类 syntax/logic/runtime/boundary/performance+输出 markdown：得分点/扣分点/改进建议），降级策略 `rule_feedback(test_results)`（按用例通过率生成中文反馈模板）；`qa_answer(course_name, knowledge_snippets, question)` 学生答疑（200 字内）；`teacher_assist(course_name, topic)` 生成课堂问题+参考答案+知识点解析；`analyze_errors(homework_id)` 班级错误统计汇总。AiUnavailable 时调用方一律走降级并正常返回
- [ ] `api/ai.py`: `POST /api/ai/qa {course_id, question, is_anonymous}`（学生，写 ai_qa_record，带 ai_knowledge_base 该课 top3 片段）；`GET /api/ai/qa/history?course_id=`；`POST /api/ai/teacher/assist {course_id, topic}`（教师备课）；`GET /api/ai/qa/hotwords?course_id=`（提问热力：高频词 top10 分组统计）；`POST /api/ai/homework/{id}/grade-all`（教师触发全量 AI 批改）；知识库 CRUD `GET/POST /api/ai/knowledge`（教师）
- [ ] Task6 的 judge_homework 完成后调用 `ai_client.grade_feedback`，失败降级 `rule_feedback`，结果写 submission_record.ai_feedback, status=2
- [ ] 冒烟：`python -c "from app.core.ai_client import chat; print(chat([{'role':'user','content':'说ok'}]))"` 返回含文本（Key 有效）；断网模拟降级单测。Run PASS
- [ ] Commit: `feat: 百炼AI答疑/批改/备课助手与降级策略`

### Task 8: 课中互动 + 辅导员 + 后台 API

**Files:** Create `app/api/interaction.py`, `app/api/counselor.py`, `app/api/admin.py`, `app/schemas/common.py`

- [ ] 课中互动（教师+学生共用前缀 /api/interaction）: `POST /api/interaction/` {course_id, interaction_type: question/rating/random_pick, student_id?, content?, score?}；`GET /api/interaction/list?course_id=&date=`；`GET /api/interaction/random-pick/{course_id}`（选课名单随机返回 1 人+写记录）；`GET /api/teacher/course/{id}/dashboard`（实时出勤+互动统计聚合）
- [ ] 辅导员（/api/counselor）: `GET /api/counselor/classes`（所辖班级）；`GET /api/counselor/warnings`（规则：出勤率<80% 或 缺勤≥3 次 或 最近作业均分低于班级均分 20 分，聚合 SQL 返回名单+指标）；`GET /api/counselor/student/{student_no}/profile`（个人学业档案：出勤统计/互动/成绩趋势）；`GET /api/counselor/stat`（所辖班级整体出勤/成绩概览）
- [ ] 后台（/api/admin，Admin 表认证，默认 admin/admin123 由 seed 写入）: 人员 CRUD（student/teacher/counselor 分页+搜索+重置密码）、班级/课程/选课管理、`GET /api/admin/stat/overview`（用户/课程/签到/提交总量+近 7 日签到趋势）、`GET /api/admin/audit`（audit_log 分页，登录/关键操作写审计）、`GET/PUT /api/ai/rules` 评分规则管理（复用 ai_scoring_rule）
- [ ] 通知: 发布作业/AI 批改完成/补签审核 写 notification；`GET /api/notification/list`、`POST /api/notification/read/{id}`
- [ ] 冒烟测试扩展 test_api_smoke.py。Run PASS
- [ ] Commit: `feat: 课中互动/辅导员预警/后台管理`

### Task 9: 前端登录页 + 学生端

**Files:** Create `web/index.html`, `web/css/style.css`, `web/js/api.js`, `web/js/common.js`, `web/student.html`

- [ ] `api.js`: `API.fetch(path,{method,body,auth:true})` 封装（自动带 Bearer、401 跳登录、解包 code/data）；`common.js`: 顶部导航/角色标签/登出/通知铃铛/消息提示 toast
- [ ] `style.css`: 统一深蓝教育风（#1e3a8a 主色），卡片/表格/按钮/模态框/toast，单文件约 300 行，四端共用
- [ ] `index.html`: 居中卡片：账号/密码/角色下拉（自动尝试）→ 存 localStorage token/role → 按角色跳转
- [ ] `student.html`（顶栏+左侧菜单 SPA 风格，原生 JS hash 路由）:
  - 我的课程（选课列表+出勤率）
  - 人脸注册（getUserMedia 摄像头→canvas 截图 b64→注册；已注册显示"已注册"，face_regen_allowed=1 时可重拍）
  - 签到中心（进行中会话卡片：课程名/剩余时间/教师距离显示；按钮"拍照并签到"→geolocation+摄像头→提交→结果三步显示：人脸相似度/距离/指纹(未启用)）
  - 作业列表（状态/截止/我的得分）→ 详情（题目描述+公开用例+代码编辑器 textarea+语言选择+提交→轮询评测结果+AI 反馈 markdown 渲染）
  - AI 答疑（匿名开关，问题→回答流式体验可简化为 loading→一次性）
  - 我的（出勤统计/成绩趋势简易条形图 canvas/通知列表）
- [ ] 手测：登录 2024001/123456 → 四菜单可切换 → 摄像头/定位授权 → 签到提交返回明确业务码（无模板时提示注册）。Commit: `feat: 登录页与学生端`

### Task 10: 前端教师端

**Files:** Create `web/teacher.html`

- [ ] 教学驾驶舱首页（我的课程+今日课表+各课出勤率）
- [ ] 发起签到（选课程→获取本机 geolocation→范围 200/时长 5 分钟→开始→进入实时看板：名单表格 10s 轮询，状态色块 正常绿/迟到黄/缺勤灰/待复核红；一键结束；补签审核列表 approve/reject）
- [ ] 作业管理（创建作业表单：标题/描述/语言/截止/总分+测试用例动态行：输入/期望输出/权重/公开；列表→提交情况→一键查重→AI 批改全部→错题统计）
- [ ] 课堂互动（随机点名大转盘简化为高亮动画；提问记录录入；星级评分；互动历史）
- [ ] AI 助手（输入知识点→生成课堂问题+参考答案；提问热词展示）
- [ ] 手测走通：发起签到→另一浏览器学生签到→看板状态变化。Commit: `feat: 教师端`

### Task 11: 前端辅导员端 + 后台

**Files:** Create `web/counselor.html`, `web/admin.html`

- [ ] `counselor.html`: 所辖班级概览→预警名单表（出勤率/缺勤次数/成绩偏差列+预警类型标签）→学生档案页（出勤日历热力简化为月表格、成绩趋势、互动记录）
- [ ] `admin.html`: 侧栏统计看板（数字卡片+近 7 日签到柱状 canvas）/人员管理四 Tab（学生/教师/辅导员：分页表格+新增/编辑/重置密码/禁用）/课程管理（课程+班级+选课关系）/审计日志/AI 规则（ai_scoring_rule 列表编辑）
- [ ] 手测两端登录与核心页。Commit: `feat: 辅导员端与后台管理端`

### Task 12: seed_demo + main.py + 端到端

**Files:** Create `scripts/seed_demo.py`, `main.py`, `tests/test_api_smoke.py` 完善, `README.md`

- [ ] `seed_demo.py`（幂等，人员不动）：admin/admin123；为 4 个无人脸学生提示（不造假人脸）；Schedule 每课 2 节；作业 3 道（A+B 最大公约数 python 权重用例 3 个含隐藏；学生成绩字符串反转；水仙花数）；历史数据：过去 14 天每课 80% 随机出勤+互动 20 条+ai_qa_record 样例+grade_book；打印账号清单
- [ ] `main.py`（唯一入口）:
```python
流程: 1) 逐个 import 检查 requirements，缺失→subprocess pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
2) 确保数据库可连（失败提示 MySQL 未启动）
3) exec scripts/init_db.py 逻辑（import 调用其 main()）
4) --seed 参数→seed_demo.main()
5) uvicorn.run("app.main:app"... 需 app/main.py 组装 FastAPI(static web/, 全部 router, exception handlers, CORS))
6) webbrowser.open("http://127.0.0.1:8000")（服务启动线程后延迟 1.5s）
7) 控制台打印四端地址+默认账号
```
另建 `app/main.py`: FastAPI 实例+挂路由+StaticFiles(web)+CORS
- [ ] `test_api_smoke.py`: TestClient 全链路——admin 登录→学生登录→人脸注册(用 cv2 生成含人脸合成图可跳过断言仅 400 码)→签到缺模板明确报错→作业创建/提交 python 代码→评测得分正确→AI 降级路径。Run: `pytest -v` 全绿
- [ ] 端到端手测：`python main.py --seed` 一条命令起全站，浏览器自动打开，四角色登录各功能可用
- [ ] `README.md`: 启动方式/默认账号/架构图/常见问题（模型首次下载/浏览器摄像头授权需 localhost/https）
- [ ] Commit: `feat: 一键启动/种子数据/端到端验证` + tag v1.0

---

## Self-Review 结论

- 申报书覆盖：签到(改人脸+定位+指纹预留)✓ 课中看板/点名/互动✓ 作业评测+AI批改+查重✓ 辅导员预警✓ 后台✓ 审计/通知/登录锁定✓ 微信小程序→静态网页(用户指定)✓
- 无占位符；类型/路径/接口名全计划一致；每任务含测试与提交
