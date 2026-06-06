# GateFlow 前端重构：React → Jinja2 + htmx

> 日期：2026-06-06
> 状态：已完成
> 目标：消除前后端分离，单进程单端口，项目结构扁平化

## 背景

GateFlow 是一个中等复杂度的 AI 网关管理后台（9 个页面，30 个 API，约 2600 行 TSX）。前后端分离带来了额外的开发负担：

- Node.js 24 + Vite + TypeScript 构建链（3692 个模块，构建产物 2.3MB）
- 双进程启动（uvicorn + vite dev server）
- CORS / 代理配置
- API 调用层（Axios 拦截器、token 管理）
- 类型定义重复（后端 Pydantic schema ↔ 前端 TypeScript interface）
- 目录嵌套（`backend/app/` 多了一层无意义的嵌套）

项目规模不需要 SPA，改为服务端渲染，项目结构扁平化。

## 目标架构

```
D:\APP\GateFlow\                    # 项目根目录（原 backend/ 内容提升）
├── app/
│   ├── templates/                  # Jinja2 模板
│   ├── static/                     # CSS/JS
│   ├── routers/                    # API 路由 + 页面路由
│   ├── services/                   # 业务逻辑
│   ├── models/                     # SQLAlchemy 模型
│   ├── middleware/                  # 认证 + session
│   ├── schemas/                    # Pydantic schema
│   └── main.py                     # FastAPI 应用入口
├── tests/                          # pytest 测试
├── requirements.txt                # Python 依赖
├── start.bat                       # 启动脚本（只需启动后端）
└── docs/                           # 文档
```

**不再有 `frontend/` 和 `backend/` 分离。一个进程，一个端口。**

## 技术选型

| 组件 | 方案 | 引入方式 |
|------|------|---------|
| 模板引擎 | Jinja2 | pip install（FastAPI 原生支持） |
| 交互增强 | htmx 2.0 | CDN `<script src="...">` |
| 样式 | Tailwind CSS v4 | CDN Play `<script src="...">` |
| 图表 | ECharts 5 | CDN `<script src="...">` |
| 聊天流式 | 原生 fetch + ReadableStream | 独立 `chat.js` |
| 认证 | httpOnly cookie session | 新增 middleware |

## 页面清单（10 个页面，全部迁移）

| # | 路由 | 页面 | 复杂度 | 关键功能 |
|---|------|------|--------|---------|
| 1 | /pages/login | 登录 | 低 | 表单提交、cookie 设置 |
| 2 | /pages/chat | AI 对话 | 高 | 流式 SSE、会话管理、乐观更新 |
| 3 | /pages/dashboard | 全局看板 | 中 | 统计卡片 + 2 个 ECharts 图表 |
| 4 | /pages/my-usage | 个人用量 | 中 | 统计卡片 + 2 个 ECharts 图表 |
| 5 | /pages/gateway | 大模型管理 | 中 | 双 Tab CRUD（模型配置 + Provider Key） |
| 6 | /pages/users | 人员管理 | 中 | 双 Tab CRUD（用户 + 部门） |
| 7 | /pages/audit | LLM 调用日志 | 中 | 筛选 + 分页表格 |
| 8 | /pages/usage | 使用统计 | 高 | 4 维度 Tab + 2 个 ECharts 图表 |
| 9 | /pages/api-keys | API Key | 中 | CRUD + 一次性展示完整 Key |
| 10 | /pages/backup | 数据库备份 | 低 | 设置表单 + 备份触发 + 历史列表 |

**完成标准：所有现有前端功能 1:1 迁移，无遗漏。**

---

## 实施阶段

### Phase 1：目录扁平化（任务 #11）

**先做这个。** 把 `backend/` 下所有内容提升到项目根目录，消除无意义的嵌套。后续所有新文件直接创建在正确位置。

- 1.1 移动 `backend/app/` → `app/`
- 1.2 移动 `backend/tests/` → `tests/`
- 1.3 移动 `backend/requirements.txt` → `requirements.txt`
- 1.4 移动 `backend/pytest.ini` → `pytest.ini`（如有）
- 1.5 移动 `backend/.env` → `.env`（如有）
- 1.6 更新 `start.bat`：工作目录改为项目根目录
- 1.7 更新 `app/config.py` 中的路径引用（如有）
- 1.8 更新 `app/database.py` 中的路径引用（如有）
- 1.9 运行 pytest 确认迁移无破坏
- 1.10 删除空的 `backend/` 目录

### Phase 2：基础设施搭建（任务 #12）

在扁平化后的结构上搭建 Jinja2 + htmx + Tailwind 基础设施。

- 2.1 安装依赖：`jinja2`, `python-multipart`
- 2.2 创建 `app/templates/` 和 `app/static/` 目录
- 2.3 配置 `app/main.py`：挂载 StaticFiles、初始化 Jinja2Templates、注册 pages 路由
- 2.4 创建 `app/routers/pages.py`：页面路由骨架
- 2.5 创建 `app/templates/base.html`：Tailwind CDN + htmx CDN + 侧边栏 + 顶栏
- 2.6 创建 `app/templates/_components.html`：Jinja2 宏
- 2.7 创建 `app/static/css/app.css`：自定义样式
- 2.8 创建 `app/static/js/app.js`：htmx 配置

### Phase 3：认证改造（任务 #13）

页面需要 cookie session 认证，先于页面迁移完成。

- 3.1 创建 `app/middleware/session.py`：服务端 session 管理
- 3.2 登录端点改造：成功后设置 httpOnly cookie
- 3.3 页面路由添加认证依赖
- 3.4 API 路由保持 JWT 不变

### Phase 4：简单页面迁移（任务 #14）

- 4.1 `login.html` — 登录表单
- 4.2 `backup.html` — 备份设置 + 立即备份 + 历史表格
- 4.3 `audit.html` — 筛选表单 + 分页表格
- 4.4 `api_keys.html` — CRUD 表格 + Modal
- 4.5 `users.html` — 双 Tab CRUD

### Phase 5：中等页面迁移（任务 #15）

- 5.1 `gateway.html` — 双 Tab CRUD
- 5.2 `dashboard.html` — 统计卡片 + ECharts
- 5.3 `user_dashboard.html` — 统计卡片 + ECharts

### Phase 6：复杂页面迁移（任务 #16）

- 6.1 `usage.html` — 4 维度 Tab + ECharts
- 6.2 `chat.html` + `chat.js` — 流式聊天

### Phase 7：清理 + 测试 + 部署脚本 + 文档（任务 #24）

- 7.1 删除 `frontend/` 目录
- 7.2 更新 `start.bat`：只需启动 uvicorn（移除前端进程、更新工作目录）
- 7.3 更新 `.gitignore`：移除 `frontend/node_modules` 等前端条目
- 7.4 更新 `requirements.txt`：确认 jinja2、python-multipart 已加入
- 7.5 测试更新：
  - 修复因目录扁平化导致的 import 路径问题（如有）
  - 新增页面路由测试（`tests/routers/test_pages.py`）：各页面 GET 返回 200 + 正确 HTML
  - 新增 session 认证测试：cookie 设置、未认证重定向、权限控制
  - 确保所有现有 pytest 测试通过
- 7.6 更新 `CLAUDE.md`：移除前端技术栈、更新架构说明和常用命令
- 7.7 废弃旧前端计划文档 `docs/superpowers/plans/2026-06-04-gateflow-frontend.md`
- 7.8 更新 `docs/superpowers/plans/2026-06-05-gateflow-p1-p2-backlog.md`
- 7.9 运行 pytest 最终验证（全量通过）
- 7.10 标记本计划为「已完成」

---

## 关键设计决策

### htmx 交互模式

**表格分页 + 筛选：** 后端返回 `<tr>` 片段，htmx `hx-get` 替换 tbody。
**CRUD 表单：** htmx `hx-post` 提交，成功返回更新行 HTML，失败返回带错误的 form fragment。
**Modal 弹窗：** HTML `<dialog>` 元素 + htmx 加载表单内容。

### 认证改造

页面路由用 cookie session，API 路由（`/api/*`、`/v1/*`）保持 JWT，两套共存互不影响。

### ECharts

CDN 引入，vanilla JS 初始化，从 API 获取数据。不引入任何前端框架。

---

## 完成标准

1. 所有 10 个页面可通过 `http://localhost:8000/pages/*` 访问
2. 所有 CRUD 操作正常（创建/编辑/删除/列表/筛选/分页）
3. 聊天页面流式消息正常
4. ECharts 图表正确渲染
5. 登录/退出/权限控制正常
6. `/api/*` 和 `/v1/*` 端点行为不变（pytest 全部通过）
7. `frontend/` 目录已删除
8. `backend/` 目录嵌套已消除
9. `start.bat` 只启动一个进程
10. 所有相关文档已更新
