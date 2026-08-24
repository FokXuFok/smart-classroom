# 全流程智慧课堂系统

面向高校课堂的"教-学-评-管"一体化单机演示系统：覆盖 **教师发起签到 → 学生人脸+定位签到 → 课堂互动 → 编程作业在线评测 → AI 批改反馈 → 学业预警 → 辅导员/管理员管理** 的全流程闭环。

对应申报书说明：原"三重核验"调整为 **人脸识别（InsightFace）+ 定位围栏（200 米）+ 指纹核验（接口预留）** 的双重实人核验 + 指纹扩展位方案。

## 快速开始

```bash
python main.py --seed
```

- **依赖自动安装**：缺失的包会自动经清华镜像 `pip install -r requirements.txt`（使用当前解释器）。
- **首次运行会自动下载人脸模型**（InsightFace buffalo_l，约 100MB+），下载慢见下方"常见问题"。
- 浏览器需 **允许摄像头与定位**（localhost / 127.0.0.1 下可用；定位不可用时可在发起签到时使用默认坐标演示）。
- 启动后自动打开 `http://127.0.0.1:8000/`；加 `--no-browser` 不自动开浏览器，`--port 8100` 换端口。
- `--seed` 只写入演示数据（幂等，**绝不改动已有人员数据**），可重复执行。

前置条件：

1. 本机 MySQL 已启动，库 `smart_classroom` 已创建（首次运行自动增量建表）。
2. 复制 `.env.example` 为 `.env`，填入数据库密码等真实值（`.env` 不入库，模板见 [.env.example](.env.example)）。数据库 / JWT 密钥 / AI Key 均从 `.env` 读取。
3. 健康检查：启动后访问 `http://127.0.0.1:8000/api/health`，返回 `db: true` 即数据库连通正常。

## 演示账号

| 角色 | 账号 | 密码 | 入口 |
| --- | --- | --- | --- |
| 管理员 | admin | admin123 | /admin.html |
| 教师 | T001、T002 | 123456 | /teacher.html |
| 辅导员 | C001、C002 | 123456 | /counselor.html |
| 学生 | 2024001~2024004、2451200817 | 123456 | /student.html |

人脸说明：**2451200817 已有人脸模板**可直接参与人脸签到；其余学生首次使用需在学生端"人脸注册"页面上传本人照片。

## 目录结构

```
├── main.py                  # 一键启动（依赖检查→DB检查→增量建表→可选种子→uvicorn）
├── config.py                # 全局配置（从 .env 读取 DB_URL/JWT/AI Key；签到阈值等）
├── .env.example             # 环境变量模板（复制为 .env 填真实值，.env 不入库）
├── requirements.txt
├── app/
│   ├── main.py              # FastAPI 入口：API 路由优先 + /uploads + web 静态托管
│   ├── api/                 # 路由：auth/student/teacher/counselor/admin/homework/interaction/ai/notification
│   ├── core/
│   │   ├── face_engine.py   # InsightFace 人脸引擎（嵌入/比对/两帧活体）
│   │   ├── geofence.py      # Haversine 定位围栏
│   │   ├── fingerprint.py   # 指纹核验（预留）
│   │   ├── ai_client.py     # 阿里百炼（OpenAI 兼容）AI 客户端
│   │   ├── security.py      # bcrypt + JWT
│   │   └── judge/           # 本地沙箱评测 + 判分/成绩册/AI 反馈/查重
│   ├── models/              # SQLAlchemy ORM（与线上库字段一致）
│   └── schemas/             # Pydantic 请求模型
├── scripts/
│   ├── init_db.py           # 数据库增量升级（幂等，只补不删）
│   └── seed_demo.py         # 演示种子数据（幂等）
├── web/                     # 四端静态前端（index/student/teacher/counselor/admin）
├── uploads/                 # 签到自拍/人脸照片等上传文件（/uploads 鉴权访问）
├── logs/                    # 运行日志（按天滚动，保留 14 天；不入库）
└── tests/                   # pytest（104 用例）
```

## 技术栈 / 架构

- **单体架构**：FastAPI + Uvicorn 单进程；MySQL（SQLAlchemy ORM）；前端为原生 HTML/JS 静态页，由 FastAPI StaticFiles 直接托管。
- **签到核心**：InsightFace（buffalo_l，ONNXRuntime）512 维人脸嵌入余弦比对（阈值 0.40）+ Haversine 200 米定位围栏 + 相似度不足转人工复核；指纹核验接口预留不阻断。
- **作业评测**：本地沙箱子进程运行（Python 开箱即用，C/Java 需系统编译器），按用例权重计分，成绩册取历史最高分；阿里百炼 AI 生成 markdown 批改反馈，AI 不可用自动降级为规则反馈；3-gram Jaccard 代码查重。
- **AI**：阿里百炼 OpenAI 兼容接口（deepseek-v4-pro-0813），Key 从 `.env` 的 `DASHSCOPE_API_KEY` 读取。
- **日志**：结构化日志（含 8 位请求 ID，贯穿签到/评测/AI 链路），控制台 + `logs/app.log` 按天滚动保留 14 天；每个 API 响应头带 `X-Request-ID`，演示出问题时可按 ID 精确定位。

## 常见问题

- **MySQL 连不上**：确认服务已启动（Windows：`net start mysql` 或服务管理器），账号/密码/端口与 `.env` 的 `DB_URL` 一致，库 `smart_classroom` 存在。可用 `/api/health` 验证连通性。
- **人脸模型下载慢**：手动下载 buffalo_l 放置到 `~/.insightface/models/buffalo_l`（Windows 即 `C:\Users\<用户名>\.insightface\models\buffalo_l`）。
- **评测 C/Java 作业**：需本机安装 `gcc` / `javac` 并在 PATH 中；Python 用例开箱即用。
- **AI 不可用**：自动降级为规则反馈（不影响评测与得分），Key 失效请在 `.env` 中更新 `DASHSCOPE_API_KEY` 后重启服务。
- **Docker Runner**：生产环境建议替换 `app/core/judge/runner.py` 为容器沙箱执行，当前本地子进程模式仅限演示。
- **浏览器拿不到定位**：localhost 下 Chrome/Edge 允许定位；仍失败时教师端可用"默认坐标"发起，学生端输入坐标演示。

## 测试

```bash
python -m pytest tests/ -q
```

当前 104 个用例全部通过（签到鉴权、人脸引擎、围栏、作业评测、预警、管理端等）。

## 安全注意

以下均为**本地演示口径**，仅限单机演示使用；上生产前必须逐项整改：

- 数据库密码、AI Key、**JWT SECRET_KEY** 均存于本地 `.env`（已 gitignore、不入库），生产请改用密钥管理服务并更换 SECRET；
- JWT 登出已失效：token 带 `jti`，登出即加入内存黑名单（服务重启黑名单清空，但 `instance_id` 同步变更，旧 token 依然全部失效）。黑名单为单进程内存版，多进程/多实例部署需换 Redis；
- `/uploads` 已改为鉴权接口（`app/api/files.py`）：未登录 401，路径越界 404，登录后同路径可直接访问（前端与库中 URL 零改动）；
- 评测沙箱为本地子进程隔离（黑名单防护），生产必须切换预留的 Docker Runner（`--network=none` 强隔离）；
- CORS 当前 `allow_origins=["*"]`，生产需配置真实域名白名单并启用 HTTPS。
