# 智慧课堂 Vue 3 多端工程 · 本次工作总结

把单页 HTML 演示(`web/`)升级为 Vue 3 多端工程(`frontend/`),覆盖教师/辅导员/管理三端。后端配套修复了种子脚本缺陷 + 补了批量通知端点。

---

## 阶段 A · 脚手架 + 登录闭环

### 前端工程(`frontend/`)

- Vite + TypeScript + Vue 3 + Element Plus + Pinia + Vue Router + axios
- `vite.config.ts`:代理 `/api → 8000`、AutoImport、Components(ElementPlusResolver)、host 0.0.0.0(修复 127.0.0.1 访问)
- `src/api/http.ts`:axios 实例 + 请求拦截器注入 `X-Role` 头(从 sessionStorage 读)+ 响应拦截器按 `json.code` 分流(`0` 返 data / `401` 跳登录 / 其他 toast)
- `src/stores/auth.ts`:Pinia store,login/logout/fetchMe,sessionStorage 持久化(key `sc-auth`)
- `src/stores/notification.ts`:5 秒轮询 `/api/notification/list`,新消息 ElNotification 横幅
- `src/router/index.ts`:守卫(未登录跳 `/login?redirect=`,角色不匹配跳自己首页),三端路由分流(`/teacher/*`、`/counselor/*`、`/admin/*`)
- `src/layouts/MainLayout.vue`:el-container + 侧栏(按 role 菜单派生)+ 顶栏(UserChip + NotificationBell)
- `src/views/auth/Login.vue`:登录表单 + 演示账号快捷填充
- `src/styles/`:沿用 `web/css/style.css` 的 CSS 变量(深蓝 #16337a × 琥珀橙 #f59e0b)+ Element Plus 主题覆盖

### 后端配套修复(为前端能跑)

- 创建 `.env`(MySQL 密码 `Wang12345`)
- 重建库 `smart_classroom`,collation 改为 `utf8mb4_0900_ai_ci`(修复外键 collation 冲突,原 `utf8mb4_unicode_ci` 与表定义 `utf8mb4_0900_ai_ci` 不兼容)
- `pip install --user -r requirements.txt`(绕过 sandbox 写系统 `C:\Python314\Scripts\` 的限制)
- **新建 `scripts/seed_base.py`**:补全基础数据(教师 T001/T002、辅导员 C001/C002、班级 CLS001/CLS002、课程 CS101/CS102/CS103、学生 2024001~2024004 + 2451200817、选课、辅导员管班)— 原 `seed_demo.py` 缺这些,全新库种子时 `schedule` 外键失败
- **修改 `scripts/seed_demo.py`**:`main()` 在 `seed_admin` 后调 `seed_base`,修复 commit 顺序(按外键依赖层级 commit)

### 验证

admin/admin123、T001/123456、C001/123456、2024001/123456 全部登录成功;cookie + X-Role 鉴权链路通;通知铃铛轮询工作;无 JS 运行时错误。

---

## 阶段 B · 教师签到 + 看板 SSE

### 新增文件

- `src/api/teacher.ts`(9 端点:myCourses / startCheckin / endCheckin / listSessions / dashboard / exportUrl / reviewAttendance / allowFaceRegen)
- `src/composables/useCheckinStream.ts`:`@microsoft/fetch-event-source` 封装,带 X-Role 头,处理 `snapshot`/`checkin`/`review`/`review_done`/`session_end` 5 事件,指数退避重连(原生 EventSource 不支持自定义头)
- `src/composables/useGeolocation.ts`(高精度定位,10 秒超时)+ `useDownload.ts`(a 标签下载,带 cookie)+ `useECharts.ts`(按需 import + init/resize/dispose)
- `src/components/StatCard.vue`(统计卡)+ `EChart.vue`(通用 ECharts 容器)

### 页面(5 个)

- `TeacherOverview.vue`:4 统计卡(教授课程/签到会话/进行中/累计签到人次)+ 趋势 BarChart + 课程占比 PieChart
- `TeacherCheckin.vue`:发起签到(选课程/时长/围栏/定位采集/默认坐标)+ 会话列表 + 结束 + 看板入口
- `CheckinDashboard.vue`:看板(4 统计卡 + SSE 实时动态 + 学生表 + 审核弹备注 + 导出 Excel)
- `CheckinReview.vue`:聚合所有进行中会话的待复核记录 + 批量审核
- `CheckinExport.vue`:会话列表 + Excel 下载

### 验证

发起签到(CS101, 30 分, 默认坐标)→ 看板 SSE 收到 snapshot;Python 模拟学生 demo 签到(2451200817 / 2024001 / 2024002)→ 看板无需刷新:动态区新增签到事件 + 学生表状态"未签到"→"正常" + 统计卡已签到 0→1→2→3 同步刷新。

---

## 阶段 C · 教师作业/课程/学生/互动

### 新增文件

- `src/api/homework.ts`(12 端点:list/detail/create/update/delete/submissions/gradebook/export/similarity/rejudge/openFeedback)
- `src/api/interaction.ts`(4 端点:create/list/randomPick/stats)

### 页面(5 个)

- `HomeworkList.vue`:作业列表(选课筛选 + 查重/重评/成绩册导出/删除)
- `HomeworkEdit.vue`:作业编辑(基本信息 + 测试用例动态行 + 编程语言下拉 + 截止时间)
- `TeacherCourses.vue`:我的课程表(只读)
- `TeacherStudents.vue`:选课程 + 选会话 → dashboard 学生名单 + 授权人脸重注册
- `TeacherInteract.vue`:随机点名 + 3 统计卡 + 类型 PieChart + Top10 BarChart + 互动历史表

### 修复

- `MainLayout.vue` 去掉 `<transition>`(作业保存跳转时 `renderSlot null.ce` 渲染崩溃,transition + 组件切换时机冲突)
- `HomeworkEdit.vue` 改用 `router.replace('/teacher/homework')`(替代 `router.back()`)

### 验证

演示作业 A/B 显示;新建"测试作业E2E"+"修复验证作业"成功(跳转后列表 111 节点正常渲染,无 null.ce 错误);课程列表 CS101/CS102;随机点名(林雨欣)+ 3 统计卡 + 2 ECharts;学生名单 5 人 + 授权重注册按钮。

---

## 阶段 D · 辅导员端

### 后端补丁(必要)

- `app/api/counselor.py` 新增 `POST /api/counselor/notify`:`NotifyReq` 支持 `class_ids`(按班级发)+ `student_nos`(按学生发,二选一),内部复用 `push_many` 单事务写入,校验班级/学生归属。原 `notification.py` 只有 list/read/read-all,无发送端点。

### 新增文件

- `src/api/counselor.ts`(6 端点:classes/students/warnings/profile/stat/notify)
- `src/api/types.ts` 扩展(CounselorClass/CounselorStudent/WarningRow/StudentProfile/CounselorStat/NotifyResult)

### 页面(7 个)

- `CounselorOverview.vue`:4 统计卡(管辖班级/学生总数/平均出勤率/预警学生数)+ 预警学生出勤率横向 BarChart(升序,<80% 红色)
- `CounselorWarnings.vue`:预警学生详表(学号/姓名/班级/出勤率/缺勤/作业均分)+ reasons 红色徽章
- `CounselorStudents.vue`:选班级 + 搜索 → 学生名单 → 选学生看档案(基本信息 + 出勤率环形 el-progress + 最近考勤表 + 成绩趋势 LineChart)
- `CounselorClasses.vue`:管辖班级表
- `CounselorAttendance.vue`:班级概览表 + 预警学生出勤率 BarChart
- `CounselorNotify.vue`:选班级多选 + 标题/内容 → 群发
- `CounselorBatch.vue`:预警学生勾选 + 标题/内容 → 批量推送(用 student_nos 精确通知)

### 验证

统计(班级 1 / 学生 5 / 出勤率 88.1% / 预警 4);预警 4 学生(林雨欣/赵明/周婷/霍旭晖,缺勤 5/3/4/3 次);学生档案(陈思远 出勤率 93% 环形 + 最近考勤 + 成绩 LineChart);群发 CLS001 → toast"已通知 5 名学生";批量勾选 2 学生 → toast"已通知 2 名学生"。

---

## 整体成果

| 维度 | 内容 |
|---|---|
| 前端工程 | `frontend/`(Vue 3 + TS + Vite + Element Plus),独立 `npm run dev` 跑 5173 |
| API 层 | 9 模块(http/auth/teacher/homework/interaction/counselor/notification + types) |
| Stores | 2(auth/sessionStorage 持久化、notification/5 秒轮询) |
| Views | 教师 10 + 辅导员 7 + 管理占位 + 登录 + 404 |
| Components | 7(MainLayout/BlankLayout/NotificationBell/UserChip/PageHeader/StatCard/EChart) |
| Composables | 4(useCheckinStream/useGeolocation/useDownload/useECharts) |
| 后端补丁 | 2 处必要补丁(seed_base 补全种子 + counselor /notify 批量通知端点),其余后端零改动 |
| 路由分流 | 三端 `/teacher/*`、`/counselor/*`、`/admin/*`,共用 MainLayout |

## dev 启动

```powershell
# 后端(8000)
python main.py --seed --no-browser

# 前端(5173,代理 /api → 8000)
cd frontend
npm install
npm run dev

# 浏览器访问 http://127.0.0.1:5173/
```

## 演示账号

| 角色 | 账号 | 密码 | 入口 |
|---|---|---|---|
| 管理员 | admin | admin123 | /admin/overview(占位,待阶段 E) |
| 教师 | T001 / T002 | 123456 | /teacher/overview |
| 辅导员 | C001 / C002 | 123456 | /counselor/overview |
| 学生 | 2024001~2024004 / 2451200817 | 123456 | (后续小程序) |

## 剩余:阶段 E(管理端)

按 plan,阶段 E 做管理端 8 页:AdminOverview(8 统计卡)+ AdminUsers(用户 CRUD + 审批)+ AdminCourses + AdminClasses + AdminEnrollments + AdminSchedules + AdminAudit + AdminStats。需先读 `app/api/admin.py`。

## 压缩包说明

- 文件:`smart-classroom-vue3.zip`
- 包含:整个项目(前端 frontend/ + 后端 app/ + 修复的 scripts/ + .env.example + 本说明)
- 排除:node_modules / dist / __pycache__ / logs / .git / *.pyc / 压缩包自身
- **注**:`.env`(含真实 MySQL 密码)未入包(已在 .gitignore,敏感不入包)。解压后需复制 `.env.example` 为 `.env` 填真实值才能起后端。
