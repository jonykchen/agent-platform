# 企业级 Agent 平台技术方案文档

> **架构定版**：Python 编排 + Java 核心服务 + 国内 LLM  
> **版本**：v2.1  
> **日期**：2026-05-09  
> **状态**：✅ 已实施

---

## 实施状态摘要

| 服务 | 实现程度 | 核心功能 | 测试状态 |
|------|----------|----------|----------|
| **orchestrator-python** | ✅ 完成 | LangGraph 状态机、工具客户端、会话存储、Checkpoint | ✅ 单元+集成 |
| **model-gateway-python** | ✅ 完成 | 智能路由、Fallback、熔断器、Token 计量、成本计算 | ✅ 单元+集成 |
| **tool-bus-java** | ✅ 完成 | gRPC 服务端、工具注册、权限校验、Mock 执行 | ✅ 单元测试 |
| **governance-java** | ✅ 完成 | 风控规则引擎、审批服务、通知服务 | ✅ 单元测试 |
| **gateway-java** | ✅ 完成 | API 入口、JWT 鉴权、租户隔离、Fast Path | ✅ 单元测试 |
| **knowledge-python** | ✅ 完成 | 文档处理、混合检索、重排序 | ✅ 单元+集成 |
| **web-frontend** | ✅ 完成 | 对话界面、审批中心、工具管理、Dashboard | ✅ E2E (Playwright) |

**契约文件**: ✅ OpenAPI、Proto、Events 已定义  
**Kubernetes**: ✅ 部署配置已创建  
**Docker**: ✅ 所有服务 Dockerfile 已创建  
**基础设施**: ✅ docker-compose、prometheus、otel-collector 配置已创建

---

## 文档导航

### 快速启动

| 文档 | 内容概要 |
|---|---|
| [quick-start.md](./quick-start.md) | **快速启动指南** — 前置要求、一键启动基础设施、各服务启动命令、常见问题 |

### Agent 开发

| 文档 | 内容概要 |
|---|---|
| [agent-dev-guide.md](./agent-dev-guide.md) | **Agent 开发指南** — 新人上手，包含核心概念、代码结构、节点开发、工具开发、测试指南 |

### 技术方案

| 序号 | 文档 | 内容概要 | 状态 |
|---|---|---|---|
| 0 | [00-index.md](./00-index.md) | **本文档** — 总览、架构、目标 | ✅ 完成 |
| 1 | [01-engineering-standards.md](./01-engineering-standards.md) | 工程规范：Monorepo结构/代码分层/错误码/日志规范 | ✅ 完成 |
| 2 | [02-communication-contracts.md](./02-communication-contracts.md) | 通信契约：Protobuf定义/接口规范/API版本治理/工具注册 | ✅ 完成 |
| 3 | [03-security-specification.md](./03-security-specification.md) | 安全规范：审计防删/Prompt注入/密钥管理/脱敏/权限模型 | ✅ 完成 |
| 4 | [04-data-design-complete.md](./04-data-design-complete.md) | 数据设计：完整DDL(含修正)/迁移策略/分区归档/多租户扩展表 | ✅ 完成 |
| 5 | [05-performance-optimization.md](./05-performance-optimization.md) | 性能优化：快速路径/RAG并行化/熔断器/批量写入/连接池矩阵 | ✅ 完成 |
| 6 | [06-operability-guide.md](./06-operability-guide.md) | 运维指南：配置管理/FeatureFlag/CI-CD/GracefulShutdown/服务发现 | ✅ 完成 |
| 7 | [07-scalability-patterns.md](./07-scalability-patterns.md) | 扩展性：多租户架构/Provider抽象/工具动态注册/水平扩展/契约测试 | ✅ 完成 |
| 8 | [08-main-technical-design.md](./08-main-technical-design.md) | **主技术方案**（原 v1.0 完整内容，含所有章节） | ✅ 完成 |
| 9 | [09-frontend-design.md](./09-frontend-design.md) | **前端设计**：对话界面、审批中心、工具管理、Dashboard | ✅ 完成 |

---

## 文档维护流程

```
方案补充 → 代码实现 → 验证通过 → 更新文档状态
```

### 状态标记说明

| 状态 | 含义 | 触发条件 |
|---|---|---|
| `✅ 完成` | 方案已定稿，可进入编码阶段 | 架构评审通过 |
| `🔧 编码中` | 正在按此方案实现代码 | 开发任务已分配 |
| `🧪 测试中` | 代码已实现，正在验证 | 功能开发完成 |
| `⚠️ 待更新` | 方案需根据验证结果调整 | 发现设计问题 |
| `❌ 废弃` | 此方案不再适用 | 技术选型变更 |

---

## 快速开始

**如果你是第一次阅读本技术方案，推荐顺序：**

1. 先读 **[00-index.md](./00-index.md)** 了解整体架构和建设目标
2. 再读 **[01-engineering-standards.md](./01-engineering-standards.md)** 掌握代码组织规范
3. 根据职责深入：
   - **后端开发** → 02 + 04 + 05
   - **AI/算法** → 05 + 07 + 原方案的 §17-18
   - **安全/运维** → 03 + 06
   - **架构师/TL** → 全部

---

## 变更记录

| 版本 | 日期 | 变更说明 |
|---|---|---|
| v1.0 | 2026-05-08 | 初版，基于技术讨论输出完整单文件方案（3517行） |
| v2.0 | 2026-05-08 | 拆分为 9 个专题文件，补充 26 项生产级工程细节 |
| v2.1 | 2026-05-09 | 新增前端设计文档（09-frontend-design.md），所有服务实现完成，状态更新为已实施 |
