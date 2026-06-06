# Changelog

所有重要变更记录在此。格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added
- Anthropic 兼容协议支持（`POST /v1/messages`）+ Provider Adapter 架构
- 按客户端类型（agent_type）维度统计用量
- 用量趋势端点 `GET /api/usage/trend`
- 审计日志详情端点 `GET /api/audit/logs/{id}`
- 普通用户用量看板（独立接口、页面、菜单）
- 部门管理（增删改）
- 修改密码功能
- 用户端 API Key 管理页面
- Chat 页流式输出（打字机效果）
- 后端 Chat 流式输出端点
- 用量统计页 Tabs 切换（模型 / 部门 / 用户 / 客户端）
- Provider API Key 池按可用 key 自动故障转移
- **加密基础设施**：Fernet 对称加密 + HMAC-SHA256 工具（`utils/crypto.py` / `utils/hashing.py`）
- **每请求 UUID** 中间件（`utils/request_id.py`），跨日志关联，响应头回显 `X-Request-ID`
- **启动 fail-fast 检查**（`utils/startup_checks.py`）：JWT_SECRET_KEY 占位符 / 长度校验
- **错误响应安全工具**（`utils/errors.py`）：固定文案 + request_id，不泄露内部异常

### Changed
- **重命名**：`app/routers/gateway.py` → `app/routers/model_configs.py`（路径前缀 `/api/gateway/models` 不变），消除与 `gateway_forward.py` 的命名混淆
- **DRY auth_middleware**：抽 `_resolve_credentials(credentials, db) -> (User, api_key_id, agent_type)` 共享 helper，`get_current_user` / `get_auth_context` 都基于它。**附带修复**：JWT 路径用显式 `UUID(sub)` 转换，SQLite 测试环境也能跑通（之前依赖 PG 隐式转换）
- **DRY Anthropic bridge**：`StreamForwarder.forward()` 加 `transform_chunk`（bytes→bytes）和 `error_sse`（client-protocol 错误格式）钩子；非流式路径加公共 `save_after_stream()` 方法。`anthropic_forward.py` 的 80 行 `bridge_stream` 闭包删除，改为 `forwarder.forward(... transform_chunk=AnthropicBridgeTransformer(), error_sse=anthropic.error_sse)`，不再调用 `_save_after_stream` 私有方法
- **DRY usage_service**：抽 `_build_summary_query(dimension_field, *, include_username, group_by_extra, filters)` 静态方法，`get_summary` 4 个维度（user/department/model/api_key）从 4 段 14 行 select 缩成 4 个 4 行调用
- **DRY token 估算**：抽 `app/utils/tokens.estimate_tokens(messages)` 工具（CHARS_PER_TOKEN=3 启发式），替换 chat_service / gateway_service / anthropic_forward 三处重复实现。**附带改进**：Anthropic content block 列表（`[{"type":"text","text":"..."}]`）现在被正确求和，旧 inline 版本用 `str(content)` 强制转换会把 `None`/`int` 等错误类型估成 1 token
- README 重写为「核心能力 + 技术栈」风格
- 用量统计改为从 AuditLog 实时聚合，删除 `UsageStat` 聚合表
- 审计日志新增 `api_key_name` 快照字段，所有统计维度（user / department / api_key）均基于 audit_log 快照聚合，保证历史不可变
- **API Key 存储**：`key` 明文 → `key_hash`（HMAC-SHA256）+ `key_prefix`（明文前 11 字符）。`APIKeyResponse` 只返 `key_prefix`；`APIKeyCreated` 一次性返完整明文
- **ProviderAPIKey 存储**：`key` 明文 → `encrypted_key`（Fernet 密文）+ `key_preview`（前 4 + ... + 后 4）。`ProviderKeyResponse` 只返 `key_preview`
- **审计日志 body**：`request_body` 明文 → Fernet 加密（条件写入，由 `AUDIT_LOG_FULL_BODY` 控制）；新增 `request_body_preview`（前 80 字符，短 body 完整、超长 head40...tail37 截断）
- **审计日志访问控制**：`GET /api/audit/logs/{id}` 默认不返回 body；`?include_body=true` 仅 admin 可用，每次访问写 meta-audit（路径 `/admin/audit-access`）
- **CORS**：从硬编码 `localhost:3000` 改为读 `ALLOWED_ORIGINS` 环境变量
- **DB engine**：`pool_size=20 / max_overflow=20 / pool_pre_ping=True / pool_recycle=1800s`（可通过 env 调整）
- **异常处理**：6 处 `str(e)` 透传给客户端的代码改为 `logger.error` + 固定文案 + request_id

### Fixed
- 修复前后端分页格式不一致
- 修复 Chat 页面模型字段和对话创建
- 修复 auth 中间件懒加载与 chat/gateway 流式保存的 race condition（AI 消息"消失"问题）
- 修复测试发现的 7 个 bug

### Security
- **P0-1**：启动时检测 JWT_SECRET_KEY 是否为占位符 / 长度 < 32 字符，发现即 fail-fast
- **P0-2**：上游 API Key 与客户端 API Key 不再明文存储，list 接口不再返回明文完整 Key
- **P0-3**：审计日志完整 body 不再明文持久化；默认不通过 API 返回；admin 访问 body 每次留痕
- **P0-4**：6 处 `str(e)` / `response.text` 透传给客户端的代码已修复，避免泄露内部异常细节
- **P0-5**：DB 连接池显式配置（防 stale 连接 + 突发流量耗尽）；CORS allow_origins 改为环境变量（避免生产锁死 localhost）
