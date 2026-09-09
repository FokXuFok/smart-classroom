# 更新日志

## 2026-09-09 Vue3 教师端 AI 助教模块 + 大学合班授课模型 + 登录注册

### 新增功能

#### 1. AI 助教（Vue3 教师端）
- 新增 `TeacherAI.vue` 页（侧栏"AI 助教"，路由 `/teacher/ai`），四类能力：
  - **AI 备课助手**：输入主题生成备课内容
  - **答疑热词**：统计本课学生提问高频词
  - **作业错误分析 Agent**：聚合错误样本，生成"高频错误统计 + 讲评建议"
  - **知识库 / 评分规则 CRUD**：管理 AI 参考与判分依据
- 新增 `frontend/src/api/ai.ts` 统一封装上述接口
- 后端新增 `POST /api/ai/homework/{id}/analyze-errors`（编译错误 / 未通过用例，剥离 expected 答案防复述，单次上限 30 条提交，AI 不可用返回 6001）

#### 2. 作业 AI 批量批改 + 反馈开放
- 作业列表新增"更多"操作：**AI 整批批改**（对已评测提交批量生成 AI 反馈，失败自动降级规则反馈）
- 新增**提交列表**、**成绩册**两个弹窗（免跳页查看评测结果 / 历史最高分）
- 新增**开放 AI 反馈**：可提前向学生开放某作业的 AI 批改反馈

#### 3. 课堂互动登记（提问 / 评分）
- 点名互动页新增"记录互动"卡片：选课程 → 记录提问或 1-5 分评分 → 入互动历史与统计

#### 4. 登录注册（Vue3 登录页）
- 新增"注册"标签页：学生/教师身份自选，学生需选行政班；提交待管理员审批通过后方可登录

#### 5. 大学合班授课模型（我的课程 · 上课安排）
- 新增 `GET /api/teacher/courses/teaching`：以**课程**为一行聚合（选课人数 = 课程全部选课，教室/上课时间 = 课表该课程多时段并集）
- 重构 `TeacherCourses.vue`：去掉按班级拆行/筛选，一门课一行展示学分/学时/选课人数/教室（多教室 tag）/上课时间（多时段 + 周次）；支持课程代码/名称关键词搜索
- 适配高校多个行政班合班上课的实际场景（桂林信息科技学院），后续改动均按此模型

### 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/api/ai.py` | 修改 | 新增 analyze-errors 班级错误分析端点 |
| `app/api/teacher.py` | 修改 | 新增 /courses/teaching 课程聚合上课安排 |
| `frontend/src/views/teacher/TeacherAI.vue` | 新增 | AI 助教页 |
| `frontend/src/api/ai.ts` | 新增 | AI 接口封装 |
| `frontend/src/api/types.ts` | 修改 | AI/上课安排/看板等类型 |
| `frontend/src/router/routes.ts` | 修改 | 注册 AI 助教路由 |
| `frontend/src/views/auth/Login.vue` | 修改 | 注册标签页 |
| `frontend/src/views/teacher/HomeworkList.vue` | 修改 | AI 整批批改 / 提交列表 / 成绩册弹窗 / 开放反馈 |
| `frontend/src/views/teacher/TeacherInteract.vue` | 修改 | 互动登记卡片 |
| `frontend/src/views/teacher/TeacherCourses.vue` | 修改 | 上课安排(按课程聚合) |
| `README.md` | 修改 | 同步说明 |

## 2026-09-08 签到防代签：二维码核验替代两帧活体（commit dbb44d9）

- 教师发起签到生成随机 qr_token 二维码投影大屏；学生拍照须将**屏幕二维码与本人脸部一起拍入画面**，后端 cv2.QRCodeDetector 从照片解码比对（内容带 `SC:` 前缀），失败抛 2008 硬阻断不入库，杜绝离线照片/翻拍旧照代签
- 签到主流程简化为 **选课 → 防重 → 人脸模板 → 地理围栏 → 人脸比对 → 指纹 → 二维码 → 正常/迟到**
- 教师端（Vue3 + web/HTML）弹出二维码大图，三端适配；后端依赖 python qrcode（SVG，无需 Pillow）
- 学生端 active 接口绝不返回 qr_token/qr_url；demo 模式（image_b64='demo'）跳过二维码核验
- 测试新增 4 例（合计 120 例）

## 2026-09-06 微信小程序适配 + 端口架构重构 + 教师签到定位优化

### 新增功能

#### 1. 微信小程序学生端（WeChatapp/WeChatAPP）
- 新增完整的微信小程序学生端，支持登录、首页课程展示、签到、通知查看
- `config.js` 自动判断运行环境：模拟器用 `127.0.0.1:8080`，真机用电脑 WLAN IP
- `utils/request.js` 手动管理 Cookie（解决 `wx.request` 对 `SameSite=Lax` cookie 自动管理不稳定的问题）
- 从响应头提取 `Set-Cookie`，按角色存储 `sc_token_student`，每次请求手动拼 `Cookie` 头

#### 2. 端口转发脚本（scripts/port_forward.py）
- 独立 TCP 端口转发脚本：`0.0.0.0:8080` → `127.0.0.1:8000`
- 让微信小程序通过 8080 端口访问后端 8000
- 双向数据转发，支持多并发连接

#### 3. main.py 一键启动 + 自动清理残留进程
- **启动前自动清理**：检查并 taskkill 占用 8000/5173/8080 端口的残留进程，彻底解决 `Errno 10048` 端口占用
- **一键启动三端口**：`python main.py` 同时启动后端 8000 + Vue3 前端 5173 + 端口转发 8080
- **退出时自动关闭**：Ctrl+C 退出时连带关闭前端 dev 和端口转发的子进程
- 新增参数：`--no-forward`（不启动端口转发）、`--forward-port`（自定义转发端口）

### 改进优化

#### 教师端签到定位（web/teacher.html）
- 新增"跳过定位"复选框：勾选后直接用默认坐标发起签到，不等待定位
- 定位超时从 10 秒缩短到 5 秒（含 5.5 秒兜底超时防止 Promise 卡死）
- 增加 `navigator.geolocation` 存在性检查（非 HTTPS 环境优雅降级）
- 实时状态提示：定位过程中显示"正在获取…"/"定位成功"/"定位失败"
- 定位失败不再弹 alert 打断流程，静默回退默认坐标

#### 端口配置统一调整
| 组件 | 端口 | 说明 |
|------|------|------|
| 后端 FastAPI | 8000 | Vue3 前端、旧 HTML 前端直接访问 |
| Vue3 前端 (Vite) | 5173 | 代理 /api → 127.0.0.1:8000 |
| 端口转发 | 8080 → 8000 | 微信小程序访问 |

配置文件更新：
- `main.py`：默认端口 8000，新增端口转发启动逻辑
- `frontend/vite.config.ts`：代理目标 → 127.0.0.1:8000
- `frontend/.env.development`：注释更新为 8000
- `web/js/api.js`：旧 HTML 前端 API_BASE → 127.0.0.1:8000
- `WeChatapp/WeChatAPP/config.js`：模拟器 127.0.0.1:8080，真机 WLAN_IP:8080

### 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `main.py` | 修改 | 端口 8000 + 自动清理残留进程 + 一键启动端口转发 |
| `web/teacher.html` | 修改 | 签到定位优化（跳过定位 + 5 秒超时 + 实时状态） |
| `scripts/port_forward.py` | 新增 | 8080→8000 TCP 端口转发脚本 |
| `WeChatapp/WeChatAPP/` | 新增 | 微信小程序学生端完整代码 |
| `.gitignore` | 修改 | 忽略 Vite timestamp 缓存文件 |

### 用法

```bash
# 一键启动全部服务（后端 + 前端 + 端口转发）
python main.py

# 只启动后端和前端，不启动端口转发
python main.py --no-forward

# 自定义端口转发
python main.py --forward-port 9090
```

### 注意事项
- 端口转发脚本（8080→8000）随 main.py 一起启动和关闭，无需单独运行
- Edge 浏览器已为 `127.0.0.1:8000` 和 `127.0.0.1:8080` 开放定位权限
- 微信小程序真机预览需手机和电脑连接同一手机热点
