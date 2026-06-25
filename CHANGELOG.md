# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- EncryptionService：AES-256-GCM 加密服务，支持密钥轮转
- Saga 分布式事务模块：CompensationRegistry + SagaState
- Dependabot 自动依赖更新配置（Maven/pip/npm/GitHub Actions）
- Stale Bot 自动标记不活跃 Issue/PR
- CODEOWNERS 自动分配 PR Reviewer
- GitHub Release Notes 自动生成模板
- `.gitleaks.toml` 密钥泄露扫描自定义规则
- `.trivyignore` 漏洞扫描忽略规则
- `make install` 一键安装所有依赖
- 前端测试补充：authStore/useDebounce/useThrottle/useLocalStorage/useTenant/useNetworkStatus/uiStore/notificationStore/FileUpload
- Java 测试补充：AuthController/SessionController/UserController/AuthService/FastPathService/ChatController/EncryptionService
- 架构图文档：`docs/architecture-overview.md`（4 个 Mermaid 图表）
- API 参考文档：`docs/api-reference.md`
- 生产部署指南：`docs/deployment-guide.md`

### 变更
- 开源准备：添加 AGPL-3.0 LICENSE、CONTRIBUTING.md、SECURITY.md、CODE_OF_CONDUCT.md
- 添加 `.env.example` 环境变量模板
- 配置校验增强：空密码/弱密码在非开发环境被拒绝
- 清理所有硬编码密钥默认值（`dev_password` → `CHANGE_ME` / 环境变量）
- README 重构：添加 CI 徽章、使用示例、文档链接
- `make ci` 完整性提升：`lint test` → `lint build test`
- JaCoCo 覆盖率阈值：0.00 → 0.30
- knowledge-python 添加 mypy strict + pytest-cov 配置
- OpenAPI servers 配置修正
- 文档编号冲突修复（10-llm-eval → 15-llm-eval）
- 所有 13 个核心文档状态更新为「已实施」
- 端口一致性修复（Tool Bus gRPC: 50051 → 40051, Orchestrator gRPC: 50051 → 50100）
- Actuator 安全配置：`show-details: always` → `when-authorized`
- CORS 安全配置：环境变量驱动 allow_origins

## [0.5.0] - 2026-06

### 新增
- Batch 5+6：测试覆盖 + 基础设施与 CI 加固
- gRPC 服务端支持（Orchestrator 端口 50100）
- GitHub Actions CI 完整流水线（Lint → Test → Security Scan → Docker Build → Deploy）

### 变更
- Batch 4：代码质量与去重优化
- 升级 protobuf 6.30+ / grpcio 1.81+

### 修复
- Batch 3：安全与基础设施加固
- Batch 2：HIGH 正确性修复
- 修复 15 个失败单元测试 + Python 3.12 name mangling + OTel 兼容

## [0.4.0] - 2026-05

### 新增
- Knowledge 服务：Rerank/Query 改写接入检索流
- Gateway：安全响应头 + RBAC 注解化与权限入库
- Orchestrator：长时记忆、Token 级流式、审批 Kafka 闭环、LLM 摘要
- Model Gateway：流式打通、分布式限流、Embedding 端点、内容过滤、成本指标

### 修复
- Batch 1：Mock 模式生产防护 + 取消端点实现 + Refresh Token 迁移 Redis
- CORS 配置、租户隔离、安全验证修复

## [0.3.0] - 2026-04

### 新增
- 生产落地阶段三：CI/CD / 可观测 / 测试补齐 / 长时记忆验证
- 生产落地阶段二：分布式限流 / 审计触发器 / 迁移 / RAG / 缓存 / K8s 加固

### 变更
- 替换已废弃的 `datetime.utcnow()`

### 修复
- 前端错误码、权限和请求管理问题
- Java 服务多处安全问题
- DocumentUploader.tsx Tooltip 组件未导入
- deps.py 和 session.py 运行时崩溃
- Redis 连接管理优化

## [0.2.0] - 2026-03

### 新增
- 生产落地阶段一：流式链路 / CORS 统一 / 审批闭环 / 真实工具执行器 / 多 LLM
- gRPC 服务端和基础设施支持
- 摘要生成和长时记忆功能
- pytest 配置和记忆系统集成测试

### 变更
- OTel 采样率配置化和缓存 TTL 抖动优化

## [0.1.0] - 2026-02

### 新增
- 初始版本：MVP 核心功能
- Gateway (Java)：API 入口 + JWT 认证
- Orchestrator (Python)：Agent 编排 + LangGraph 状态机
- Model Gateway (Python)：多 LLM 提供商统一网关
- Tool Bus (Java)：工具执行总线（Mock 实现）
- Governance (Java)：风控 + 审批
- Knowledge (Python)：知识库服务（RAG）
- 基础设施：Docker Compose / PostgreSQL + pgvector / Redis / Kafka

[Unreleased]: https://github.com/jonykchen/agent-platform/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/jonykchen/agent-platform/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/jonykchen/agent-platform/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/jonykchen/agent-platform/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/jonykchen/agent-platform/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/jonykchen/agent-platform/releases/tag/v0.1.0
