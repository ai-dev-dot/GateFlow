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

### Changed
- README 重写为「核心能力 + 技术栈」风格
- 用量统计改为从 AuditLog 实时聚合，删除 `UsageStat` 聚合表
- 审计日志新增 `api_key_name` 快照字段，所有统计维度（user / department / api_key）均基于 audit_log 快照聚合，保证历史不可变

### Fixed
- 修复前后端分页格式不一致
- 修复 Chat 页面模型字段和对话创建
- 修复 auth 中间件懒加载与 chat/gateway 流式保存的 race condition（AI 消息"消失"问题）
- 修复测试发现的 7 个 bug
