# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

GateFlow（闸机）是企业 AI 网关 —— 所有大模型调用的统一入口，提供访问控制、成本管理、审计日志和协议转换。

## 技术栈

### 后端（Python 3.13）

| 依赖 | 版本 | 用途 |
|------|------|------|
| FastAPI | 0.136.3 | Web 框架 |
| Uvicorn | 0.48.0 | ASGI 服务器 |
| SQLAlchemy[asyncio] | 2.0.50 | ORM（async 模式） |
| asyncpg | 0.31.0 | PostgreSQL 异步驱动 |
| Pydantic | 2.13.4 | 数据校验 |
| pydantic-settings | 2.14.1 | 配置管理（.env） |
| httpx | 0.28.1 | 异步 HTTP 客户端（转发请求到上游 LLM） |
| python-jose[cryptography] | 3.5.0 | JWT 签发/验证 |
| passlib[bcrypt] + bcrypt | 1.7.4 / 4.0.1 | 密码哈希 |
| Alembic | 1.18.4 | 数据库迁移（尚未启用） |

### 前端（Node.js 24，TypeScript 5.6）

| 依赖 | 版本 | 用途 |
|------|------|------|
| React | 18.3 | UI 框架 |
| Vite | 6.0 | 构建工具 + 开发服务器 |
| React Router | 6.28 | 路由 |
| Ant Design (antd) | 5.22 | UI 组件库（中文 locale） |
| Zustand | 5.0 | 状态管理 |
| Axios | 1.7 | HTTP 客户端 |
| ECharts (echarts-for-react) | 5.5 / 3.0 | 图表 |
| dayjs | 1.11 | 日期处理 |

### 数据库

PostgreSQL（asyncpg 驱动），连接串在 `backend/.env`，参考 `.env.example`。

## 常用命令

### 后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000   # 启动开发服务器
```

表结构由 SQLAlchemy `create_all` 自动创建，启动时自动 seed 管理员账号和 AgentType 默认值。

```bash
python -m pytest tests/ -v     # 运行所有测试
python -m pytest tests/ -v -k "test_openai"  # 运行匹配的测试
```

### 前端

```bash
cd frontend
npm install
npm run dev      # Vite 开发服务器，端口 3000
npm run build    # 生产构建
```

Vite 开发模式下 `/api` 和 `/v1` 请求代理到后端 `localhost:8000`。

## 架构

### 两路请求路径

**路径 A：OpenAI 兼容网关** — `POST /v1/chat/completions`（`routers/gateway_forward.py` → `GatewayService`）
**路径 B：Anthropic 兼容网关** — `POST /v1/messages`（`routers/anthropic_forward.py` → `GatewayService`）
**路径 C：Chat 应用** — `POST /api/chat/conversations/{id}/messages/stream`（`routers/chat.py` → `ChatService`，有会话管理和消息存库）

路径 A/B 是无状态代理，路径 C 是有状态聊天应用。三者共享 `ProviderAdapter` 层处理协议差异。

### Provider Adapter 模式

`services/provider_adapters/` 使用策略模式隔离不同 LLM 提供商的协议差异：

- `BaseAdapter` — 抽象基类，定义 URL 构建、header 构建、请求体构建、SSE 解析、响应提取等接口
- `OpenAIAdapter` — OpenAI 兼容协议（默认回退）
- `AnthropicAdapter` — Anthropic Messages API 协议

新增 provider：实现 `BaseAdapter`，在 `__init__.py` 的 `_adapters` 字典注册。

### 认证

`middleware/auth_middleware.py` 提供两个依赖：
- `get_current_user()` — 返回 `User`，支持 JWT Token 和 `gf_` 前缀 API Key 双模认证
- `get_auth_context()` — 返回 `AuthContext`（含 `user`、`api_key_id`、`agent_type`），用于审计追踪

### 关键数据流（网关路径）

```
客户端 → 认证中间件 → Router → GatewayService
  → ProviderKeyService.get_available_key()  # 从连接池选可用 key
  → Adapter.build_upstream_url/headers/body  # 协议适配
  → httpx.stream/post 转发到上游
  → Adapter.parse_stream_event/extract_response  # 解析 token 用量
  → 后台任务更新 AuditLog + UsageStat
```

### 模型层

所有模型使用 UUID 主键 + `TimestampMixin`（`created_at`/`updated_at`）。核心模型：

- `ModelConfig` — 模型路由表（alias → provider + target_model + target_url）
- `ProviderAPIKey` — 上游 API Key 池（按 provider 分组，支持智能故障转移）
- `APIKey` — 客户端 API Key（`gf_` 前缀），关联 `AgentType` 标识客户端类型
- `AgentType` — 客户端类型枚举（Claude Code、Codex、Cursor 等，管理员维护）
- `AuditLog` — 请求审计（含 `api_key_id` 和 `agent_type` 用于按工具统计）

### 前端

- `api/chat.ts` 中 `sendMessageStream` 使用原生 `fetch` + `ReadableStream` 处理 SSE（axios 不支持流式）
- 前端始终期望 OpenAI 格式 SSE（`choices[].delta.content`），ChatService 内部做 Anthropic→OpenAI 转换
- Zustand 管理 auth 状态（token 存 localStorage）
- Ant Design 使用中文 locale（`zh_CN`）

## 注意事项

- 默认管理员：`admin` / `admin123`
- API Key 以 `gf_` 开头，认证中间件通过前缀区分 Key 和 JWT
- 流式响应是透传模式：网关逐块转发，流结束后异步更新审计日志和用量统计
- `GatewayService` 和 `ChatService` 的流式处理都通过 adapter 解析 SSE，不在 service 层硬编码协议逻辑
