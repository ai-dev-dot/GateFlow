# 闸机 GateFlow MVP 设计文档

> 日期：2026-06-04
> 版本：v0.1.0 MVP
> 状态：设计完成，待审阅

---

## 1. 项目概述

闸机 GateFlow 是企业内部所有大模型调用的统一入口。它帮企业管住数据泄露风险、控住 AI 使用成本、理清所有使用行为。

### 1.1 使用场景

企业用户使用 AI 主要有以下场景：

**场景一：直接问答（非技术用户）**
- 产品经理、市场、HR 等岗位直接与 AI 对话
- 需要一个类似豆包风格的问答页面
- 如果不提供，用户会绕过闸机去用公网产品，失去管控意义

**场景二：AI Agent 集成（技术用户）**
- 使用 Dify、Coze、LangChain、Cursor 等工具
- 配置 LLM API 端点指向闸机
- 我们的 OpenAI 兼容 API 天然支持

**场景三：业务系统集成（开发团队）**
- CRM、ERP、工单系统等内部系统调用 AI
- 同样通过 OpenAI 兼容 API 对接

### 1.2 MVP 目标

构建最小可用版本，跑通核心链路：
- 用户通过闸机直接与 AI 问答（问答页面）
- 用户通过闸机 API 调用大模型（Agent/系统集成）
- 管理员管理用户、配置模型路由
- 所有请求有完整日志记录
- 可以查看 Token 用量统计

### 1.3 MVP 范围

**包含：**
- 统一模型 API 网关（DeepSeek、小米 MiMo）
- **AI 问答页面（豆包风格）**
- 基础用户管理与 RBAC 权限
- 全量请求与响应日志
- Token 用量统计（不含金额计算）
- 前端管理后台

**不包含（列入后续版本）：**
- Docker 部署
- Redis（速率限制、缓存）
- 成本金额计算
- 敏感数据检测与脱敏
- 预算管理与告警
- SSO 集成（企业微信、钉钉、飞书）
- RAG 引擎
- 影子 AI 治理

---

## 2. 技术选型

| 决策项 | 选择 | 理由 |
|-------|------|------|
| 后端框架 | FastAPI + SQLAlchemy 2.0 (async) | 原生异步、流式支持好、中间件机制完善 |
| 数据库 | PostgreSQL | 功能强大、JSON 支持好、企业级首选 |
| 前端框架 | React 18 + TypeScript | 生态丰富、适合复杂管理后台 |
| UI 组件库 | Ant Design 5 | 企业级设计、组件丰富、中文文档好 |
| 认证方式 | JWT Token | 无状态、易扩展、前后端分离首选 |
| API 协议 | OpenAI 兼容格式 | 国产模型都兼容、用户无需学习新 SDK |

### 2.1 性能考量

- 瓶颈在上游 LLM API（等待响应 2-30 秒），不在网关本身
- FastAPI 异步模型在等待上游响应时可处理其他请求
- 流式响应直接透传，网关零延迟
- 未来可通过 Gunicorn 多 worker 水平扩展

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (React + Ant Design)             │
│                    http://localhost:3000                      │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP API
┌─────────────────────────▼───────────────────────────────────┐
│                    FastAPI 应用 (ASGI)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ 网关模块 │ │ 权限模块 │ │ 日志模块 │ │ 用量模块 │       │
│  │ gateway  │ │   auth   │ │  audit   │ │  usage   │       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘       │
│       │             │            │             │              │
│  ┌────▼─────────────▼────────────▼─────────────▼──────┐      │
│  │              共享层：中间件、依赖注入、配置          │      │
│  └───────────────────────┬────────────────────────────┘      │
└──────────────────────────┼───────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │      PostgreSQL         │
              │   (用户/日志/用量/配置)  │
              └─────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   大模型 API (DeepSeek,  │
              │   小米 MiMo)            │
              └─────────────────────────┘
```

### 3.2 项目目录结构

```
GateFlow/
├── backend/                        # 后端 FastAPI 应用
│   ├── app/
│   │   ├── main.py                # 应用入口
│   │   ├── config.py              # 配置管理
│   │   ├── database.py            # 数据库连接
│   │   ├── models/                # SQLAlchemy 数据模型
│   │   │   ├── user.py            # 用户、角色、权限模型
│   │   │   ├── gateway.py         # API Key、模型配置
│   │   │   ├── chat.py            # 对话、消息模型
│   │   │   ├── audit.py           # 请求日志模型
│   │   │   └── usage.py           # 用量统计模型
│   │   ├── schemas/               # Pydantic 请求/响应模型
│   │   │   ├── user.py
│   │   │   ├── gateway.py
│   │   │   ├── chat.py
│   │   │   ├── audit.py
│   │   │   └── usage.py
│   │   ├── routers/               # API 路由
│   │   │   ├── auth.py            # 登录、注册、Token
│   │   │   ├── users.py           # 用户管理
│   │   │   ├── gateway.py         # 网关转发接口
│   │   │   ├── chat.py            # 问答对话接口
│   │   │   ├── audit.py           # 审计日志查询
│   │   │   └── usage.py           # 用量统计
│   │   ├── services/              # 业务逻辑
│   │   │   ├── auth_service.py
│   │   │   ├── gateway_service.py # 核心：转发、负载均衡
│   │   │   ├── chat_service.py    # 问答对话服务
│   │   │   ├── audit_service.py
│   │   │   └── usage_service.py
│   │   ├── middleware/            # 中间件
│   │   │   ├── auth_middleware.py # JWT 认证
│   │   │   └── logging_middleware.py # 请求日志
│   │   └── utils/                 # 工具函数
│   │       ├── security.py        # JWT、密码加密
│   │       └── http_client.py     # 异步 HTTP 客户端
│   ├── alembic/                   # 数据库迁移
│   ├── tests/                     # 测试
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                       # 前端 React 应用
│   ├── src/
│   │   ├── pages/                 # 页面组件
│   │   │   ├── Login.tsx          # 登录页
│   │   │   ├── Chat.tsx           # AI 问答页（豆包风格）
│   │   │   ├── Dashboard.tsx      # 控制台首页
│   │   │   ├── Gateway.tsx        # 网关管理
│   │   │   ├── Users.tsx          # 用户管理
│   │   │   ├── Audit.tsx          # 审计日志
│   │   │   └── Usage.tsx          # 用量统计
│   │   ├── components/            # 通用组件
│   │   ├── services/              # API 调用封装
│   │   ├── stores/                # 状态管理
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml              # 一键部署（后续版本）
├── .env.example                    # 环境变量模板
└── README.md
```

---

## 4. API 网关模块（核心）

### 4.1 OpenAI 兼容 API

网关提供 OpenAI 兼容的 API 接口，用户可以用 OpenAI SDK 直接对接：

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://your-gateflow:8000/v1",
    api_key="gf_user_xxx"  # 闸机发的 JWT Token
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好"}],
    temperature=0.7,
    stream=True
)
```

### 4.2 支持的 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 对话补全（核心） |
| `/v1/models` | GET | 获取可用模型列表 |

### 4.3 路由逻辑

```
用户请求: POST /v1/chat/completions
         model="deepseek-chat"
              │
              ▼
    ┌─────────────────┐
    │  解析 model 参数 │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐     找到配置
    │ 查询模型路由配置 ├──────────────┐
    └────────┬────────┘              │
             │ 未找到                ▼
             ▼              ┌─────────────────┐
    返回 404 错误           │ 选择可用 API Key │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │ 转发到目标 API   │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │ 记录日志 + 统计  │
                            └────────┬────────┘
                                     │
                                     ▼
                            返回响应给用户
```

### 4.4 模型路由配置

数据库存储模型路由配置：

| 字段 | 类型 | 说明 | 示例 |
|-----|------|------|------|
| id | UUID | 主键 | - |
| model_alias | string | 用户请求的模型名 | `deepseek-chat` |
| provider | string | 提供商标识 | `deepseek` |
| target_url | string | 实际 API 地址 | `https://api.deepseek.com/v1` |
| api_keys | JSON | API Key 池 | `["sk-xxx", "sk-yyy"]` |
| is_active | bool | 是否启用 | `true` |
| rate_limit | int | 速率限制 (req/min) | `60` |
| created_at | datetime | 创建时间 | - |

### 4.5 流式响应处理

采用直接透传策略，网关零延迟：

```python
async def stream_response(upstream_response):
    async for chunk in upstream_response.aiter_bytes():
        yield chunk  # 收到一块就转发一块
```

### 4.6 协议设计

- **统一入口协议**：OpenAI 兼容格式
- **MVP 阶段**：DeepSeek、小米 MiMo 都支持 OpenAI 格式，直接透传
- **未来扩展**：需要支持其他协议时，在网关层加协议转换器

### 4.7 参数透传

网关是透明代理，用户请求中的参数（temperature、max_tokens、top_p 等）原样转发给上游 API。

管理员可在权限层面设置约束（如某些用户 max_tokens 上限），但不限制协议层面的参数。

---

## 5. 用户与权限管理模块

### 5.1 数据模型

**User（用户）**

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | UUID | 主键 |
| username | string | 用户名（唯一） |
| email | string | 邮箱（唯一） |
| hashed_password | string | 加密后的密码 |
| department_id | UUID | 所属部门 |
| role_id | UUID | 角色 |
| is_active | bool | 是否启用 |
| created_at | datetime | 创建时间 |
| last_login | datetime | 最后登录时间 |

**Role（角色）**

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | UUID | 主键 |
| name | string | 角色名（admin/user/viewer） |
| permissions | JSON | 权限列表 |

**Department（部门）**

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | UUID | 主键 |
| name | string | 部门名 |
| parent_id | UUID | 上级部门（支持树形结构） |

### 5.2 RBAC 权限（MVP 简化版）

| 角色 | 权限 |
|------|------|
| **admin** | 全部权限：用户管理、模型配置、查看所有日志、用量统计 |
| **user** | 调用 API、查看自己的日志和用量 |
| **viewer** | 只读：查看日志和统计，不能调用 API |

### 5.3 认证流程

```
1. 用户登录: POST /api/auth/login
   → 验证用户名密码
   → 返回 JWT Token (有效期 24h)

2. API 调用: POST /v1/chat/completions
   → Header: Authorization: Bearer <jwt_token>
   → 中间件验证 Token
   → 提取 user_id、role、permissions
   → 检查权限

3. Token 刷新: POST /api/auth/refresh
   → 用旧 Token 换新 Token
```

### 5.4 JWT Token 结构

```json
{
    "sub": "user_id",
    "username": "zhangsan",
    "role": "user",
    "department_id": "dept_001",
    "exp": 1234567890
}
```

### 5.5 管理员账号初始化

系统首次启动时自动创建默认管理员：
- 用户名：`admin`
- 密码：`admin123`
- 角色：admin（超级管理员）
- 首次登录后强制修改密码

配置文件可自定义默认管理员邮箱和密码。

---

## 6. 审计日志模块

### 6.1 日志记录内容

每次 API 调用记录以下信息：

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | UUID | 主键 |
| timestamp | datetime | 请求时间 |
| user_id | UUID | 用户 ID |
| username | string | 用户名 |
| department | string | 部门名 |
| model | string | 请求的模型 |
| provider | string | 提供商 |
| method | string | HTTP 方法 |
| path | string | 请求路径 |
| request_body | text | 请求体（完整记录） |
| request_tokens | int | 输入 Token 数 |
| response_tokens | int | 输出 Token 数 |
| total_tokens | int | 总 Token 数 |
| latency_ms | int | 响应耗时（毫秒） |
| status_code | int | HTTP 状态码 |
| is_stream | bool | 是否流式请求 |
| ip_address | string | 客户端 IP |
| user_agent | string | 客户端 User-Agent |

### 6.2 日志查询 API

```
GET /api/audit/logs?
    user_id=xxx          # 按用户筛选
    &department=技术部    # 按部门筛选
    &model=deepseek-chat # 按模型筛选
    &start_time=...      # 时间范围
    &end_time=...
    &page=1
    &page_size=20
```

### 6.3 敏感数据处理

- MVP 阶段：记录完整请求和响应（企业内部使用，需要完整审计）
- 后续迭代：可配置脱敏规则（手机号、身份证号自动打码）

---

## 7. 用量统计模块

### 7.1 统计维度

MVP 阶段只统计 Token 用量和各维度占比，金额计算列入后续版本。

**统计维度：**
- Token 用量（输入/输出分开统计）
- 模型占比（哪个模型用得最多）
- 用户占比（谁用得最多）
- 部门占比（哪个部门用得最多）
- 请求次数统计

### 7.2 统计 API

```
GET /api/usage/summary?
    dimension=user        # 按用户统计
    &start_time=...
    &end_time=...

GET /api/usage/summary?
    dimension=department  # 按部门统计
    &start_time=...
    &end_time=...

GET /api/usage/summary?
    dimension=model       # 按模型统计
    &start_time=...
    &end_time=...
```

### 7.3 返回示例

```json
{
    "dimension": "department",
    "period": "2026-06",
    "data": [
        {
            "name": "技术部",
            "total_requests": 12500,
            "input_tokens": 3200000,
            "output_tokens": 2000000,
            "total_tokens": 5200000
        },
        {
            "name": "产品部",
            "total_requests": 3200,
            "input_tokens": 700000,
            "output_tokens": 400000,
            "total_tokens": 1100000
        }
    ]
}
```

---

## 8. 前端设计

### 8.1 页面列表

| 页面 | 路由 | 说明 | 权限 |
|------|------|------|------|
| 登录页 | `/login` | 用户名/密码登录 | 公开 |
| **AI 问答页** | `/chat` | **豆包风格对话界面** | **所有用户** |
| 控制台首页 | `/dashboard` | 用量概览、趋势图 | 所有用户 |
| 网关管理 | `/gateway` | 模型路由配置、API Key 管理 | admin |
| 用户管理 | `/users` | 用户增删改查、角色分配 | admin |
| 审计日志 | `/audit` | 日志列表、详情查看 | admin/user |
| 用量统计 | `/usage` | Token 用量统计图表 | 所有用户 |

### 8.2 AI 问答页设计（豆包风格）

**布局：**
```
┌──────────────────────────────────────────────────────┐
│  侧边栏          │        主对话区域                   │
│                  │                                    │
│  [+ 新对话]      │  ┌────────────────────────────┐   │
│                  │  │ 模型: [deepseek-chat ▼]    │   │
│  历史对话列表    │  └────────────────────────────┘   │
│  ├ 今天          │                                    │
│  │ ├ 对话1       │  ┌────────────────────────────┐   │
│  │ └ 对话2       │  │ 🤖 你好！我是闸机 AI 助手  │   │
│  ├ 昨天          │  │    有什么可以帮你的？       │   │
│  │ └ 对话3       │  └────────────────────────────┘   │
│  └ 更早          │                                    │
│                  │  ┌────────────────────────────┐   │
│                  │  │ 👤 帮我写一封邮件           │   │
│                  │  └────────────────────────────┘   │
│                  │                                    │
│                  │  ┌────────────────────────────┐   │
│                  │  │ [输入框]              [发送] │   │
│                  │  └────────────────────────────┘   │
└──────────────────────────────────────────────────────┘
```

**核心功能：**
- 豆包风格的对话界面
- 支持选择模型（根据用户权限显示可用模型）
- 流式输出（打字机效果）
- 对话历史保存
- 多轮对话上下文

**权限控制：**
- admin：可用所有模型
- user：根据角色配置可用模型
- viewer：只读（查看历史对话，不能新建）

**新增数据模型：**

| 模型 | 字段 | 说明 |
|------|------|------|
| Conversation | id, user_id, model, title, created_at | 对话 |
| Message | id, conversation_id, role, content, tokens, created_at | 消息 |

> 问答页面的每次对话都自动记录到审计日志，Token 用量计入统计。

### 8.3 控制台首页内容

- 今日/本周/本月请求量概览
- Token 用量趋势图（折线图）
- 模型使用占比（饼图）
- 部门用量排名（柱状图）

### 8.4 技术栈

- React 18 + TypeScript
- Ant Design 5
- Umi（蚂蚁金服企业级前端框架）
- ECharts（图表库）

---

## 9. API 接口汇总

### 9.1 认证相关

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/refresh` | POST | 刷新 Token |
| `/api/auth/password` | PUT | 修改密码 |

### 9.2 用户管理（admin）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/users` | GET | 用户列表 |
| `/api/users` | POST | 创建用户 |
| `/api/users/{id}` | PUT | 更新用户 |
| `/api/users/{id}` | DELETE | 删除用户 |
| `/api/departments` | GET | 部门列表 |
| `/api/departments` | POST | 创建部门 |

### 9.3 网关管理（admin）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/gateway/models` | GET | 模型路由列表 |
| `/api/gateway/models` | POST | 添加模型路由 |
| `/api/gateway/models/{id}` | PUT | 更新模型路由 |
| `/api/gateway/models/{id}` | DELETE | 删除模型路由 |
| `/api/gateway/api-keys` | GET | API Key 列表 |
| `/api/gateway/api-keys` | POST | 添加 API Key |

### 9.4 网关转发

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 对话补全（OpenAI 兼容） |
| `/v1/models` | GET | 可用模型列表 |

### 9.5 问答对话

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/conversations` | GET | 对话列表 |
| `/api/chat/conversations` | POST | 新建对话 |
| `/api/chat/conversations/{id}/messages` | GET | 获取对话消息 |
| `/api/chat/conversations/{id}/messages` | POST | 发送消息（流式响应） |
| `/api/chat/conversations/{id}` | DELETE | 删除对话 |

### 9.6 审计日志

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/audit/logs` | GET | 日志列表（支持筛选） |
| `/api/audit/logs/{id}` | GET | 日志详情 |

### 9.7 用量统计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/usage/summary` | GET | 用量统计（按维度） |
| `/api/usage/trend` | GET | 用量趋势 |

---

## 10. 后续版本规划

### 10.1 v0.2.0

- Docker 一键部署
- Redis 集成（速率限制、Token 黑名单）
- 成本金额计算（维护定价表）
- 敏感数据检测与脱敏
- 预算管理与告警
- 支持更多大模型（Anthropic Claude、字节豆包）

### 10.2 v0.3.0

- SSO 集成（企业微信、钉钉、飞书、LDAP）
- 协议转换层（支持 Anthropic 格式输入）
- 完善的审计检索功能
- 数据导出（Excel、CSV）

### 10.3 更远期

- 统一 RAG 引擎
- 工具调用框架
- 浏览器插件
- IDE 插件
- 影子 AI 治理

---

## 附录 A：默认管理员账号

系统首次启动时自动创建：
- 用户名：`admin`
- 密码：`admin123`
- 角色：admin（超级管理员）
- **首次登录后强制修改密码**

> 此信息需更新到 README.md 的"快速开始"章节。
