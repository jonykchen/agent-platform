# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- 开源准备：添加 AGPL-3.0 LICENSE、CONTRIBUTING.md、SECURITY.md、CODE_OF_CONDUCT.md
- 添加 `.env.example` 环境变量模板
- 配置校验增强：空密码/弱密码在非开发环境被拒绝

### 变更
- 清理所有硬编码密钥默认值（`dev_password` → `CHANGE_ME` / 环境变量）
- README 重构：添加徽章、移除内部工具配置、更新许可证声明

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

[Unreleased]: https://github.com/your-username/agent-platform/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/your-username/agent-platform/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/your-username/agent-platform/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/your-username/agent-platform/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/your-username/agent-platform/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/your-username/agent-platform/releases/tag/v0.1.0
