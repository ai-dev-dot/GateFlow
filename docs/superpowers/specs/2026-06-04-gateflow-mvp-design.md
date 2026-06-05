# 闸机 GateFlow MVP 设计文档

> 日期：2026-06-04（v0.2.0 Anthropic 支持更新于 2026-06-05）
> 版本：v0.2.0
> 状态：MVP 已完成，v0.2.0 设计完成

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

### 1.4 v0.2.0 范围

**新增：**
- **Anthropic 协议支持** —— `POST /v1/messages` 端点，Claude Code 等原生 Anthropic 客户端可直接通过闸机代理
- **Provider Adapter 架构** —— 协议差异隔离在 adapter 层，新增 provider 只需实现一个 adapter
- **客户端类型管理（AgentType）** —— 管理员维护的枚举表，创建 API Key 时选择客户端类型，审计日志按客户端类型统计 token 用量

---

## 2. 技术选型

| 决策项 | 选择 | 理由 |
|-------|------|------|
| 后端框架 | FastAPI + SQLAlchemy 2.0 (async) | 原生异步、流式支持好、中间件机制完善 |
| 数据库 | PostgreSQL | 功能强大、JSON 支持好、企业级首选 |
| 前端框架 | React 18 + TypeScript | 生态丰富、适合复杂管理后台 |
| UI 组件库 | Ant Design 5 | 企业级设计、组件丰富、中文文档好 |
| 认证方式 | JWT Token + API Key | JWT 用于前端页面，API Key 用于工具/系统集成 |
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
│   │   │   ├── api_key.py         # 用户 API Key 模型
│   │   │   ├── provider_key.py    # 上游 API Key 模型
│   │   │   ├── gateway.py         # 模型路由配置
│   │   │   ├── chat.py            # 对话、消息模型
│   │   │   ├── audit.py           # 请求日志模型
│   │   │   └── usage.py           # 用量统计模型
│   │   ├── schemas/               # Pydantic 请求/响应模型
│   │   │   ├── user.py
│   │   │   ├── api_key.py
│   │   │   ├── provider_key.py
│   │   │   ├── gateway.py
│   │   │   ├── chat.py
│   │   │   ├── audit.py
│   │   │   └── usage.py
│   │   ├── routers/               # API 路由
│   │   │   ├── auth.py            # 登录、注册、Token
│   │   │   ├── users.py           # 用户管理
│   │   │   ├── api_keys.py        # 用户 API Key 管理
│   │   │   ├── provider_keys.py   # 上游 API Key 管理
│   │   │   ├── gateway.py         # 网关转发接口
│   │   │   ├── chat.py            # 问答对话接口
│   │   │   ├── audit.py           # 审计日志查询
│   │   │   └── usage.py           # 用量统计
│   │   ├── services/              # 业务逻辑
│   │   │   ├── auth_service.py
│   │   │   ├── gateway_service.py # 核心：转发、智能调度
│   │   │   ├── provider_key_service.py # API Key 池管理
│   │   │   ├── chat_service.py    # 问答对话服务
│   │   │   ├── audit_service.py
│   │   │   └── usage_service.py
│   │   ├── middleware/            # 中间件
│   │   │   ├── auth_middleware.py # JWT + API Key 双模认证
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
    api_key="gf_xxxxxxxxxxxxxxxx"  # 在闸机后台创建的 API Key
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好"}],
    temperature=0.7,
    stream=True
)
```

### 4.2 支持的 API 端点

| 端点 | 方法 | 协议 | 说明 |
|------|------|------|------|
| `/v1/chat/completions` | POST | OpenAI | 对话补全（核心） |
| `/v1/messages` | POST | Anthropic | Anthropic Messages API（v0.2.0 新增） |
| `/v1/models` | GET | OpenAI | 获取可用模型列表 |

**双协议支持**：网关同时暴露 OpenAI 和 Anthropic 两种协议端点。客户端 SDK 自动选择对应的端点——OpenAI SDK 调用 `/v1/chat/completions`，Anthropic SDK 调用 `/v1/messages`。两个端点共享同一套认证、模型配置、审计日志和用量统计基础设施。

```python
# OpenAI SDK 配置
client = OpenAI(base_url="http://your-gateflow:8000/v1", api_key="gf_xxx")

# Anthropic SDK 配置（v0.2.0+）
client = anthropic.Anthropic(base_url="http://your-gateflow:8000/v1", api_key="gf_xxx")
```

### 4.3 路由与调度逻辑

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
    │ 查询 ModelConfig ├──────────────┐
    └────────┬────────┘              │
             │ 未找到                ▼
             ▼              ┌─────────────────┐
    返回 404 错误           │ 查询可用 API Key │
                            │ (ProviderAPIKey) │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │ 智能选择 Key     │
                            │ - 跳过已禁用     │
                            │ - 跳过已封禁     │
                            │ - 跳过冷却中     │
                            │ - 优先选错误少的 │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │ 转发到目标 API   │
                            └────────┬────────┘
                                     │
                         ┌───────────┴───────────┐
                         │                       │
                         ▼                       ▼
                    成功                    失败(429/401/5xx)
                         │                       │
                         ▼                       ▼
                ┌─────────────────┐    ┌─────────────────┐
                │ 更新 Key 统计   │    │ 自动冷却/封禁   │
                │ 重置错误计数    │    │ 记录错误信息    │
                └────────┬────────┘    └────────┬────────┘
                         │                       │
                         └───────────┬───────────┘
                                     ▼
                            ┌─────────────────┐
                            │ 记录日志 + 统计  │
                            └────────┬────────┘
                                     │
                                     ▼
                            返回响应给用户
```

**智能 Key 选择算法（MVP）：**

```python
async def get_available_api_key(provider: str) -> ProviderAPIKey:
    """获取可用的 API Key，采用故障转移策略"""
    
    keys = await db.execute(
        select(ProviderAPIKey)
        .where(
            ProviderAPIKey.provider == provider,
            ProviderAPIKey.is_active == True,
            ProviderAPIKey.is_banned == False,
            (ProviderAPIKey.cool_down_until == None) | 
            (ProviderAPIKey.cool_down_until < datetime.utcnow())
        )
        .order_by(ProviderAPIKey.consecutive_errors, ProviderAPIKey.last_used_at)
    ).scalars().all()
    
    if not keys:
        raise HTTPException(503, f"提供商 {provider} 没有可用的 API Key")
    
    return keys[0]  # 选择错误最少、最久未使用的 Key
```

**错误处理与自动冷却：**

```python
async def handle_api_key_error(key: ProviderAPIKey, error: Exception):
    key.consecutive_errors += 1
    key.last_error_at = datetime.utcnow()
    
    if isinstance(error, RateLimitError):  # 429
        key.cool_down_until = datetime.utcnow() + timedelta(minutes=1)
    elif isinstance(error, AuthenticationError):  # 401
        key.is_banned = True
        key.ban_reason = "上游返回 401 Unauthorized"
    elif key.consecutive_errors >= 10:
        key.cool_down_until = datetime.utcnow() + timedelta(minutes=10)
    
    await db.commit()
```

### 4.4 模型路由配置

**模型配置表（ModelConfig）：**

| 字段 | 类型 | 说明 | 示例 |
|-----|------|------|------|
| id | UUID | 主键 | - |
| model_alias | string | 用户请求的模型名（唯一） | `deepseek-chat` |
| provider | string | 提供商标识 | `deepseek` |
| target_model | string | 上游实际模型名 | `deepseek-chat` |
| target_url | string | 实际 API 地址 | `https://api.deepseek.com/v1` |
| is_active | bool | 是否启用 | `true` |
| priority | int | 模型优先级（数字越小越优先） | `0` |
| default_temperature | float | 默认温度参数 | `0.7` |
| default_max_tokens | int | 默认最大 token 数 | `4096` |
| created_at | datetime | 创建时间 | - |

**上游 API Key 表（ProviderAPIKey）— 独立表，非 JSON 数组：**

| 字段 | 类型 | 说明 | 示例 |
|-----|------|------|------|
| id | UUID | 主键 | - |
| provider | string | 提供商标识（索引） | `deepseek` |
| key | string(255) | 上游 API Key（唯一） | `sk-xxx...` |
| name | string | Key 名称 | `DeepSeek-企业版-1号` |
| remark | string | 备注（用途、负责人） | `技术部专用 Key` |
| is_active | bool | 是否启用（索引） | `true` |
| is_banned | bool | 是否被上游封禁 | `false` |
| ban_reason | string | 封禁原因 | - |
| rpm_limit | int | 每分钟请求数限制 | `60` |
| tpm_limit | int | 每分钟 Token 数限制 | `100000` |
| total_requests | bigint | 总请求数 | `12500` |
| total_input_tokens | bigint | 总输入 Token 数 | `5200000` |
| total_output_tokens | bigint | 总输出 Token 数 | `3100000` |
| consecutive_errors | int | 连续错误次数 | `0` |
| cool_down_until | datetime | 冷却截止时间 | - |
| created_at | datetime | 创建时间 | - |
| last_used_at | datetime | 最后使用时间（索引） | - |

**核心关系：**
- 一个 `provider` 对应多个 `ProviderAPIKey`
- 一个 `ModelConfig` 对应一个 `provider`
- API Key 与模型配置完全解耦

**为什么必须用独立表而非 JSON 数组：**
1. ✅ 可以单独启用/禁用某个 Key
2. ✅ 可以单独设置每个 Key 的速率限制
3. ✅ 可以追踪每个 Key 的用量和错误
4. ✅ 可以实现智能故障转移（自动冷却失败的 Key）
5. ✅ 可以按 Key 维度审计和统计
6. ❌ JSON 数组无法做到以上任何一点

### 4.5 流式响应处理

采用直接透传策略，网关零延迟。同时解决流式响应的日志记录问题：

**核心问题：** 流式响应的 token 数量只有在响应结束后才能统计。

**解决方案：** 先创建待处理日志，响应结束后异步更新。

```python
async def forward_stream_request(user, model, request_body):
    # 1. 先创建一个不完整的日志记录（token 数量未知）
    log_id = await audit_service.create_pending_log(
        user_id=user.id,
        model=model,
        request_body=request_body
    )
    start_time = time.time()
    
    # 2. 转发请求并流式返回
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", target_url, json=request_body) as response:
            full_response = ""
            async for chunk in response.aiter_bytes():
                yield chunk  # 收到一块就转发一块，用户无感知延迟
                full_response += chunk.decode("utf-8")
            
            # 3. 响应结束后，异步更新日志和用量统计
            await audit_service.update_log_after_response(
                log_id=log_id,
                status_code=response.status_code,
                request_tokens=count_tokens(request_body["messages"]),
                response_tokens=count_tokens(full_response),
                latency_ms=int((time.time() - start_time) * 1000)
            )
            
            # 4. 更新用户用量统计
            await usage_service.record_usage(
                user_id=user.id,
                model=model,
                input_tokens=request_tokens,
                output_tokens=response_tokens
            )
```

**日志状态流转：**
```
请求开始 → 创建日志 (status="pending", tokens=0)
    ↓
流式响应中 → 用户收到数据，日志暂不更新
    ↓
响应结束 → 更新日志 (status="completed", tokens=实际值)
```

### 4.6 协议设计

**MVP 阶段**：DeepSeek、小米 MiMo 都支持 OpenAI 格式，直接透传。

**v0.2.0 扩展**：引入 Provider Adapter 架构，支持多协议。

**核心差异（OpenAI vs Anthropic）：**

| 维度 | OpenAI | Anthropic |
|------|--------|-----------|
| 端点 | `POST /v1/chat/completions` | `POST /v1/messages` |
| 认证头 | `Authorization: Bearer <key>` | `x-api-key: <key>` |
| `max_tokens` | 可选 | **必填** |
| system prompt | messages 数组内 | 顶层 `system` 字段 |
| 流式文本 | `choices[].delta.content` | `content_block_delta` → `delta.text` |
| 流结束标记 | `data: [DONE]` | `event: message_stop` |
| 非流式响应 | `choices[0].message.content` | `content[0].text` |
| token 字段 | `usage.prompt_tokens` / `completion_tokens` | `usage.input_tokens` / `output_tokens` |

### 4.7 Provider Adapter 架构（v0.2.0）

将协议差异隔离在 adapter 层，GatewayService 和 ChatService 通过统一接口处理不同协议：

```
provider_adapters/
├── __init__.py          # get_adapter(provider) 工厂函数
├── base.py              # BaseAdapter 抽象基类 + StreamEvent 数据类
├── openai_adapter.py    # OpenAI 协议适配
└── anthropic_adapter.py # Anthropic 协议适配
```

**BaseAdapter 接口：**

```python
@dataclass
class StreamEvent:
    text: str = ""           # 本次增量文本
    input_tokens: int = 0    # 输入 token
    output_tokens: int = 0   # 输出 token
    done: bool = False       # 流是否结束
    error: str = ""          # 错误信息

class BaseAdapter(ABC):
    def build_upstream_url(self, target_url: str) -> str: ...
    def build_headers(self, api_key: str) -> dict: ...
    def build_request_body(self, body: dict, target_model: str, defaults: dict) -> dict: ...
    def extract_response(self, response: dict) -> tuple[str, int, int]: ...
    def parse_stream_event(self, lines: list[str]) -> StreamEvent: ...
    def format_error(self, status: int, body: dict) -> dict: ...
    def error_sse(self, message: str, error_type: str) -> str: ...
```

**两条路径：**

```
Claude Code → POST /v1/messages (Anthropic 格式)
                │
                ▼
        GatewayService + AnthropicAdapter
                │
                ▼
        上游 Anthropic API（透传原始格式）

Chat 页面 → POST /api/chat/.../messages/stream
                │
                ▼
        ChatService + 自动选择 adapter
                │
                ▼
        adapter 将 Anthropic 响应转换为 OpenAI SSE 格式
                │
                ▼
        前端收到 OpenAI SSE（choices[].delta.content）
```

- `/v1/messages` 端点：透传上游原始 Anthropic 格式，Claude Code 等原生客户端直接使用
- Chat 页面：ChatService 内部做 Anthropic → OpenAI 格式转换，前端无需改动

### 4.8 客户端类型管理（AgentType，v0.2.0）

管理员维护的枚举表，用于标识 API Key 的用途（哪个客户端/Agent 在使用）。

**AgentType 模型：**

| 字段 | 类型 | 说明 | 示例 |
|-----|------|------|------|
| id | UUID | 主键 | - |
| name | string(50) | 类型名称（唯一） | `Claude Code` |
| is_active | bool | 是否启用 | `true` |
| created_at | datetime | 创建时间 | - |

**内置默认值（系统初始化时自动创建）：**

| name | 说明 |
|------|------|
| Claude Code | Anthropic 官方 CLI 开发工具 |
| Codex | OpenAI 代码生成工具 |
| Cursor | AI 代码编辑器 |
| Dify | LLM 应用开发平台 |
| LangChain | LLM 应用框架 |
| 自定义 | 用户自定义用途 |

**APIKey 模型关联：**

```python
class APIKey(Base):
    # ... 现有字段 ...
    agent_type_id = Column(UUID, ForeignKey("agent_types.id"), nullable=True)
    agent_type = relationship("AgentType")
```

创建 API Key 时，用户从下拉列表中选择客户端类型。审计日志记录 `agent_type`，用量统计按客户端类型分组。

**API 接口：**

```
GET    /api/agent-types           # 获取客户端类型列表（所有用户可访问）
POST   /api/agent-types           # 新增类型（管理员）
PUT    /api/agent-types/{id}      # 编辑类型（管理员）
DELETE /api/agent-types/{id}      # 删除类型（管理员）
```

### 4.9 参数透传

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
| hashed_password | string | bcrypt 加密后的密码（60 字符） |
| department_id | UUID | 所属部门 |
| role_id | UUID | 角色 |
| is_active | bool | 是否启用 |
| created_at | datetime | 创建时间 |
| last_login | datetime | 最后登录时间 |

**密码加密实现（bcrypt）：**

```python
# utils/security.py
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)
```

**为什么用 bcrypt 而非 MD5/SHA256：**
- ❌ MD5/SHA256：太快，暴力破解容易，无盐值
- ✅ bcrypt：慢哈希（可调节计算轮数），自带盐值，抗彩虹表攻击

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

### 5.3 双模认证机制

闸机支持两种认证方式，分别服务不同场景：

| 认证方式 | 使用场景 | 特点 |
|---------|---------|------|
| **JWT Token** | 前端页面（问答、管理后台） | 有有效期（默认 7 天，后台可配置），自动刷新 |
| **API Key** | 工具/系统集成（Dify、Cursor、业务系统） | 永久有效，可随时吊销 |

**JWT Token（前端使用）：**
```
1. 用户登录: POST /api/auth/login
   → 验证用户名密码
   → 返回 JWT Token (有效期默认 7 天，可在后台配置)

2. 前端请求: 自动携带 Cookie/LocalStorage 中的 Token
   → 中间件验证 JWT
   → 提取 user_id、role、permissions
```

**API Key（工具/系统集成使用）：**
```
1. 用户在后台创建 API Key: POST /api/api-keys
   → 返回 gf_xxxxxx 格式的 Key（只显示一次）

2. 工具配置:
   base_url = "http://your-gateflow:8000/v1"
   api_key  = "gf_xxxxxx"

3. API 调用: POST /v1/chat/completions
   → Header: Authorization: Bearer gf_xxxxxx
   → 中间件识别 gf_ 前缀，走 API Key 验证
   → 查询 api_keys 表，验证 Key 有效性和权限
```

### 5.4 API Key 数据模型

**APIKey（用户 API Key）**

| 字段 | 类型 | 说明 |
|-----|------|------|
| id | UUID | 主键 |
| user_id | UUID | 所属用户 |
| name | string | Key 名称（如"我的 Cursor Key"） |
| key | string(64) | Key 值，`gf_` 前缀 + 60 位随机字符，唯一 |
| permissions | JSON | 权限列表（可限制可用模型） |
| rate_limit | int | 每分钟请求数限制 |
| expires_at | datetime | 过期时间（可选，空=永不过期） |
| is_active | bool | 是否启用 |
| created_at | datetime | 创建时间 |
| last_used_at | datetime | 最后使用时间 |

**Key 生成规则：**
```
格式: gf_ + 60位随机字符
示例: gf_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0
```

### 5.5 JWT Token 结构

```json
{
    "sub": "user_id",
    "username": "zhangsan",
    "role": "user",
    "department_id": "dept_001",
    "exp": 1234567890
}
```

### 5.6 管理员账号初始化

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
| status | string | 日志状态：`pending`（响应中）/ `completed`（已完成）/ `failed`（失败） |
| timestamp | datetime | 请求时间 |
| user_id | UUID | 用户 ID |
| username | string | 用户名 |
| department | string | 部门名 |
| api_key_id | UUID | 使用的 API Key ID（可选） |
| agent_type | string | 客户端类型（枚举值，如"Claude Code"、"Codex"，v0.2.0 新增） |
| model | string | 请求的模型 |
| provider | string | 提供商 |
| method | string | HTTP 方法 |
| path | string | 请求路径 |
| request_body | text | 请求体（完整记录） |
| request_tokens | int | 输入 Token 数（流式响应结束后更新） |
| response_tokens | int | 输出 Token 数（流式响应结束后更新） |
| total_tokens | int | 总 Token 数 |
| latency_ms | int | 响应耗时（毫秒） |
| status_code | int | HTTP 状态码 |
| is_stream | bool | 是否流式请求 |
| ip_address | string | 客户端 IP |
| user_agent | string | 客户端 User-Agent |
| created_at | datetime | 日志创建时间 |
| completed_at | datetime | 日志完成时间（流式响应结束后更新） |

**数据库索引（性能关键）：**

审计日志表数据量大（每天几十万条），必须建立以下索引：

```sql
-- 按时间查询（最常用）
CREATE INDEX idx_audit_logs_timestamp ON audit_logs (timestamp DESC);

-- 按用户查询
CREATE INDEX idx_audit_logs_user_time ON audit_logs (user_id, timestamp DESC);

-- 按部门查询
CREATE INDEX idx_audit_logs_dept_time ON audit_logs (department, timestamp DESC);

-- 按模型查询
CREATE INDEX idx_audit_logs_model_time ON audit_logs (model, timestamp DESC);

-- 按状态查询（用于查找未完成的流式响应）
CREATE INDEX idx_audit_logs_status ON audit_logs (status) WHERE status = 'pending';
```

**查询性能预期：**
- 无索引：100 万条记录查询需 5-10 秒
- 有索引：100 万条记录查询需 10-50 毫秒

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
- API Key 占比（哪个工具用得最多，v0.2.0 新增）—— 通过 `api_key_id` 关联，每个 Key 可标记用途（如"Claude Code"、"Codex"、"Cursor"）
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

GET /api/usage/summary?
    dimension=api_key     # 按 API Key 统计（v0.2.0 新增）
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
- Vite（构建工具，开发热更新 < 50ms）
- React Router v6（路由管理）
- Axios（HTTP 请求）
- Zustand（轻量状态管理）
- ECharts（图表库）

> **注：** 设计稿原定使用 Umi 框架，但 MVP 阶段改用 Vite + React Router 更轻量、更灵活。Umi 适合大型项目（50+ 页面、多团队协作），MVP 只有 7 个页面，不需要约定式路由的复杂度。后期如需迁移，成本可控。

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
| `/api/users/departments` | GET | 部门列表 |
| `/api/users/departments` | POST | 创建部门 |

### 9.3 API Key 管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/api-keys` | GET | 获取当前用户的 API Key 列表 |
| `/api/api-keys` | POST | 创建新的 API Key |
| `/api/api-keys/{id}` | PUT | 更新 API Key（名称、权限、限速） |
| `/api/api-keys/{id}` | DELETE | 吊销 API Key |

### 9.4 网关管理（admin）

**模型路由管理：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/gateway/models` | GET | 模型路由列表 |
| `/api/gateway/models` | POST | 添加模型路由 |
| `/api/gateway/models/{id}` | PUT | 更新模型路由 |
| `/api/gateway/models/{id}` | DELETE | 删除模型路由 |

**上游 API Key 管理（ProviderAPIKey）：**

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/gateway/provider-keys` | GET | 上游 API Key 列表（支持按 provider 筛选） |
| `/api/gateway/provider-keys` | POST | 添加上游 API Key |
| `/api/gateway/provider-keys/{id}` | PUT | 更新 Key（名称、备注、限速、启用/禁用） |
| `/api/gateway/provider-keys/{id}` | DELETE | 删除 Key |
| `/api/gateway/provider-keys/{id}/reset` | POST | 重置 Key 状态（清除错误计数、解封） |

### 9.5 网关转发

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/chat/completions` | POST | 对话补全（OpenAI 兼容） |
| `/v1/models` | GET | 可用模型列表 |

### 9.6 问答对话

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat/conversations` | GET | 对话列表 |
| `/api/chat/conversations` | POST | 新建对话 |
| `/api/chat/conversations/{id}/messages` | GET | 获取对话消息 |
| `/api/chat/conversations/{id}/messages` | POST | 发送消息（流式响应） |
| `/api/chat/conversations/{id}` | DELETE | 删除对话 |

### 9.7 审计日志

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/audit/logs` | GET | 日志列表（支持筛选） |
| `/api/audit/logs/{id}` | GET | 日志详情 |

### 9.8 用量统计

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/usage/summary` | GET | 用量统计（按维度） |
| `/api/usage/trend` | GET | 用量趋势 |

---

## 10. 后续版本规划

### 10.1 v0.2.0

- **Anthropic 协议支持**（`POST /v1/messages` 端点 + Provider Adapter 架构）✅ 设计完成
- **按 API Key 用量统计**（审计日志追踪 api_key_id，按工具维度统计 token）✅ 设计完成
- Docker 一键部署
- Redis 集成（速率限制、Token 黑名单）
- 成本金额计算（维护定价表）
- 敏感数据检测与脱敏
- 预算管理与告警
- 支持更多大模型（字节豆包等）

### 10.2 v0.3.0

- SSO 集成（企业微信、钉钉、飞书、LDAP）
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

---

## 附录 B：开发注意事项

以下是开发过程中容易踩的坑，提前注意可避免后期返工。

### B.1 异步任务处理

**问题：** 流式响应结束后的日志更新和用量统计，如果在同一个请求线程中处理，会阻塞最后一个 chunk 的返回。

**解决方案：** 使用 `asyncio.create_task()` 创建后台任务，不要等待它完成：

```python
async def forward_stream_request():
    # ... 转发逻辑 ...
    
    # ❌ 错误：await 会阻塞最后一个 chunk 的返回
    # await audit_service.update_log_after_response(...)
    
    # ✅ 正确：创建后台任务，不阻塞响应
    asyncio.create_task(
        audit_service.update_log_after_response(
            log_id=log_id,
            status_code=response.status_code,
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            latency_ms=latency_ms
        )
    )
    
    asyncio.create_task(
        usage_service.record_usage(
            user_id=user.id,
            model=model,
            input_tokens=request_tokens,
            output_tokens=response_tokens
        )
    )
```

### B.2 并发安全的统计更新

**问题：** 如果多个请求同时更新同一个 API Key 的统计数据，先读再写会导致数据丢失。

**解决方案：** 使用 SQLAlchemy 的原子更新，不要先查询再修改：

```python
# ❌ 错误：先读再写，并发不安全
key = await db.get(ProviderAPIKey, key_id)
key.total_requests += 1
key.total_input_tokens += input_tokens
await db.commit()

# ✅ 正确：原子更新，并发安全
await db.execute(
    update(ProviderAPIKey)
    .where(ProviderAPIKey.id == key_id)
    .values(
        total_requests=ProviderAPIKey.total_requests + 1,
        total_input_tokens=ProviderAPIKey.total_input_tokens + input_tokens,
        total_output_tokens=ProviderAPIKey.total_output_tokens + output_tokens
    )
)
await db.commit()
```

### B.3 大请求体处理

**问题：** 如果用户上传一个 10MB 的文件，完整记录到审计日志会导致数据库性能急剧下降。

**解决方案：** MVP 阶段可以先记录完整内容，但增加一个最大长度限制：

```python
MAX_LOG_CONTENT_LENGTH = 100 * 1024  # 100KB

request_body_str = json.dumps(request_body)
if len(request_body_str) > MAX_LOG_CONTENT_LENGTH:
    request_body_str = request_body_str[:MAX_LOG_CONTENT_LENGTH] + " [内容过长已截断]"
```

### B.4 数据库事务边界

**问题：** 如果在同一个事务中既更新 API Key 统计，又记录审计日志，一旦其中一个失败，会导致整个事务回滚。

**解决方案：** 把不同的操作放在不同的事务中：

- **事务 1：** 网关转发和 API Key 状态更新
- **事务 2：** 审计日志和用量统计

即使日志记录失败，也不影响用户的正常请求。

### B.5 上游响应头透传

**问题：** 很多工具依赖上游返回的 `X-RateLimit-Remaining`、`X-RateLimit-Reset` 等响应头来做速率限制处理。

**解决方案：** 在转发响应的时候，把上游的所有响应头原样透传给用户：

```python
async def forward_stream_request():
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", target_url, json=request_body) as response:
            # 透传所有响应头
            headers = dict(response.headers)
            # 删除可能有问题的头
            headers.pop("content-encoding", None)
            headers.pop("transfer-encoding", None)
            
            return StreamingResponse(
                stream_response(response),
                status_code=response.status_code,
                headers=headers
            )
```
