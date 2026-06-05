# 贡献指南

感谢你考虑为 GateFlow 做贡献！

## 开发环境

### 后端
- Python 3.13
- PostgreSQL 14+
- 推荐：uv / poetry 管理依赖

### 前端
- Node.js 24
- TypeScript 5.6+

### 启动

参见 [README 快速开始](README.md#快速开始)。

## 提交流程

1. Fork 仓库
2. 创建特性分支（`git checkout -b feat/xxx`）
3. 提交改动（commit message 建议前缀：`feat:` / `fix:` / `docs:` / `refactor:` / `test:`）
4. 推送到 fork
5. 提交 Pull Request，描述改动原因、影响范围和测试情况

## 代码规范

### 后端
- 遵循 PEP 8
- 异步优先（FastAPI + SQLAlchemy async）
- Service 层负责业务逻辑，Router 层只做参数转发和鉴权
- 数据库变更需同步更新 `app/models/` 和迁移脚本

### 前端
- TypeScript 严格模式（`strict: true`）
- React 函数组件 + Hooks，避免 class 组件
- Ant Design 组件库，使用中文 locale（`zh_CN`）
- 状态管理用 Zustand，避免 Redux 样板代码

## 架构决策

任何架构级变更（数据库表结构、API 协议、模块拆分、新增 provider）请先开 issue 讨论，
避免直接动代码。设计文档同步维护在 `docs/superpowers/specs/`。

## Bug 报告

提交 issue 时请包含：
- 复现步骤
- 预期行为 vs 实际行为
- 环境信息（后端版本、数据库版本、操作系统）
- 报错日志或截图

## 联系方式

- GitHub Issues: 公开问题、Bug、功能请求
- 详见 [SECURITY.md](SECURITY.md) 报告安全问题
