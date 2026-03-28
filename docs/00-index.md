# 企业级 Agent 平台 — 总览与架构

> 本文档为技术方案的总览索引，详细设计请参考各专题文档。

**版本**：v2.4 | **状态**：✅ 完成 | **最后更新**：2026-05-09

> **v2.4 更新**：前端功能 100% 完成，包含知识库管理、租户配置、通用组件等所有设计文档要求的功能。

> **v2.3 更新**：前端设计文档状态更新为已完成，所有 Phase 已实现（代码位于 `services/web-frontend/`）。

> **v2.2 新增**：前端设计文档（09-frontend-design.md），包含对话界面、管理后台、监控面板完整方案。

> **v2.1 修正说明**：基于架构评估报告，本版本实施 10 项关键改进：
> - **P0（编码前必解）**：Fast Path 增加安全检查、Prompt 注入防护补充中文模式、Token 配额原子化（Lua 脚本）
> - **P1（Phase 1 结束前）**：统一 Gateway→Orchestrator 为 gRPC、Redis Checkpoint TTL 心跳续期、pgvector 迁移阈值 500万→150万、Risk+Approval 合并为 governance-java
> - **P2（Phase 2 完善）**：Orchestrator Sticky Session 一致性哈希、ABAC 条件引擎沙箱化、RLS 性能基准测试

---

## 1. 建设目标

本方案用于建设一套可在生产环境稳定运行的企业级 Agent 平台：

| 目标维度 | 具体内容 |
|---|---|
| **核心能力** | 对话式任务处理、知识问答、工具调用、审批执行和业务闭环 |
| **安全保障** | 高风险动作风控拦截、人工审批、审计追踪和恢复执行 |
| **模型治理** | 多模型接入、替换、灰度发布和成本控制 |
| **系统集成** | 与现有 Java 核心业务系统平滑集成，不破坏原有交易与治理体系 |

## 2. 总体结论

采用 `Python 编排 + Java 核心服务 + 国内 LLM` 的混合架构：

| 语言 | 职责 | 理由 |
|---|---|---|
| **Python** | Agent 编排、状态机、推理链路、工具选择、RAG、会话记忆 | AI 生态主场 |
| **Java** | 统一入口、鉴权、风控、审计、交易、写库、高并发业务接口 | 企业稳定性主场 |
| **LLM** | 通过统一 Model Gateway 接入，屏蔽厂商差异 | 避免绑定单一供应商 |

## 3. 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        客户端层                                      │
│              Web / App / OpenAPI / 第三方集成                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP / WebSocket
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Gateway Service (Java)                            │
│         统一API入口 │ 鉴权 │ 限流 │ 租户 │ 请求追踪                   │
└──────┬──────────────────────┬────────────────────────────────┘
       │ 同步HTTP/gRPC         │ 审计事件/异步通知
       ▼                       ▼
┌──────────────────┐    ┌───────────────────────────┐
│ Orchestrator(Python)│   │           Kafka             │
│ ┌──────────────────┐│   │  异步/通知/回放             │
│ │ Agent状态机编排     ││   └───────────────────────────┘
│ │ 会话记忆/RAG      ││                │
│ │ 任务分解/决策     ││                │
│ └──────┬──────▲───┘ │                │
│        │       │     │                │
└────────┼───────┼─────┘                │
         │       │                      │
    同步HTTP  同步HTTP/gRPC              │
         │       │                      │
         ▼       ▼                      │
┌─────────────────┐ ┌────────────┐      │
│ Model Gateway   │ │Tool Bus(J) │◄─────┘
│ (Python)        │ │            │
│ 模型路由/超时    │ │Risk Svc    │
│ 重试/Fallback    │ │Approval Svc│
│ Token/成本统计   │ │Business    │
└─────────────────┘ └────────────┘

数据层: PostgreSQL │ Redis │ pgvector │ OSS/COS/MinIO
观测层: OpenTelemetry │ Prometheus │ Grafana │ Audit
```

## 4. 技术选型总表

| 层级 | 选型 | 版本 | 说明 |
|---|---|---|---|
| **API 入口** | Java 21 + Spring Boot 3 + Security | Boot 3.2+ | 统一鉴权/限流/租户隔离 |
| **Agent 编排** | Python 3.12 + FastAPI + LangGraph + Pydantic V2 | ≥3.12 | 多步任务/checkpoint/校验 |
| **模型网关** | Python FastAPI + httpx | ≥3.12 | 统一接入/路由/fallback/成本 |
| **工具服务** | Spring Boot 3 | JDK 21 | 业务工具/查询/写操作/审计 |
| **长任务编排** | LangGraph Checkpoint + Kafka Callback | — | 暂停/恢复/超时/重试（基于 Redis checkpoint 持久化 + Kafka 事件回调恢复） |
| **事件总线** | Kafka 3.6+ | — | 异步/解耦/回放（初期可 Redis Stream）|
| **主数据库** | PostgreSQL 16+ | — | 运行态/审计/配置/任务 |
| **缓存** | Redis 7+ | — | 会话态/缓存/幂等/分布式锁 |
| **向量检索** | pgvector 0.7+ | — | 起步用，>150万块迁移 Qdrant（v2.1修正） |
| **文件存储** | MinIO/COS/OSS | — | 文档/附件/工具产物 |
| **配置中心** | Nacos/Apollo | — | 统一配置管理 |
| **Service Mesh** | Istio 1.20+ on K8s | — | mTLS/金丝雀/熔断/镜像 |
| **观测** | OTel 1.30+ + Prom + Grafana | — | 全链路tracing/指标/告警 |

## 5. 服务职责一览

| 服务 | 语言 | 核心职责 | 关键能力 |
|---|---|---|---|
| **gateway-java** | Java | 统一 API 入口 | 鉴权/限流/租户/追踪/快速路径 |
| **orchestrator-python** | Python | Agent 编排引擎 | 状态机/RAG/记忆/工具决策/审批中断 |
| **model-gateway-python** | Python | 模型统一网关 | 厂商适配/路由/弹性/格式标准化/流式 |
| **tool-bus-java** | Java | 工具总线 | 注册/校验/执行代理/结果规范化 |
| **governance-java** | Java | 风控+审批（MVP合并） | 规则引擎/行为检测/审批流/通知推送/恢复触发 |
| **knowledge-python** | Python | 知识库服务 | 文档处理/向量化/检索/重排/权限 |

## 6. 模型分工矩阵

| 角色 | 模型 | 定位 | 占比 |
|---|---|---|---|
| **主模型** | Qwen (通义千问) | 通用问答/工具调用/结构化输出 | ~60% |
| **强推理备** | GLM-5 / DeepSeek | 复杂规划/多步决策/难样本兜底 | ~25% |
| **多模态** | Kimi K2.5 | 长文档理解/图片/视频分析 | ~15% |

## 7. 核心质量门槛

| 指标 | 目标值 | 关键依赖 |
|---|---|---|
| JSON 合法率 | ≥ 99.5% | schema 校验 + 重试 |
| 工具调用成功率 | ≥ 98% | 工具本身稳定性 |
| 高风险误执行率 | = 0 | 风控 + 审批强制 |
| 简单问答 P95 | < 6s | 流式输出 + 快速路径(目标<3s) |
| 单工具任务 P95 | < 15s | gRPC + 连接池 + 并行调用 |
| 系统可用性 | ≥ 99.9% | HA 拓扑 + 灾备 |
| 审批等待 P50 | < 30min | 审批人响应效率 |

## 8. 实施路线图

```
2026 Q2          2026 Q3           2026 Q4          2027 Q1+
  │                 │                 │                 │
  ▼                 ▼                 ▼                 ▼
┌────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Phase1 │───▶│ Phase 2  │───▶│ Phase 3  │───▶│ Phase 4  │
│ MVP    │    │ 业务闭环  │    │ 能力增强  │    │ 规模化   │
│ 4周    │    │ 8周      │    │ 8周      │    │ 持续     │
└────────┘    └──────────┘    └──────────┘    └──────────┘
```

| Phase | 时间 | 核心交付物 | 成功标准 |
|---|---|---|---|
| **Phase 1: MVP** | 第 1-4 周 | Gateway+Orchestrator+ModelGateway+Mock ToolBus | E2E 跑通，request_id 贯穿 |
| **Phase 2: 业务闭环** | 第 5-12 周 | 真实工具+风控+审批+Kafka回调恢复 | 高风险必审批，Gold Set ≥30条 |
| **Phase 3: 能力增强** | 第 13-20 周 | RAG知识库+多模态+评测体系+灰度 | Recall@10≥85%，CI 融入评测 |
| **Phase 4: 规模化** | 第 21 周+ | 多租户完整隔离+成本治理+自进化 | RTO≤30min，10x 用户量 |

---

## 9. 专题文档索引（改进项对照）

以下专题文档对应两轮架构审查中识别出的 **26 项具体改进点**：

### 🔴 Critical — 编码前必须解决（9 项）

| 改进编号 | 问题 | 所在文档 | 章节 |
|---|---|---|---|
| **C-01** | Python 服务内部分层缺失 | [01-engineering-standards.md](./01-engineering-standards.md) | §2.2 Orchestrator 完整包结构 |
| **C-02** | Java 服务包结构未定义 | [01-engineering-standards.md](./01-engineering-standards.md) | §2.3 Gateway/ToolBus 标准包结构 |
| **C-03** | Monorepo 工程基础设施零 | [01-engineering-standards.md](./01-engineering-standards.md) | §3 Makefile/buf/editorconfig/tool-versions |
| **C-04** | 统一错误码协议缺失 | [02-communication-contracts.md](./02-communication-contracts.md) | §2 ErrorCode 枚举定义(ErrorDetail) |
| **P-01** | 请求链路无快速路径(Fast Path) | [05-performance-optimization.md](./05-performance-optimization.md) | §2 Gateway Streaming Proxy 设计 |
| **S-01** | 审计表防删改机制无效 | [03-security-specification.md](./03-security-specification.md) | §2 触发器强制阻断方案 |
| **S-02** | Prompt 注入防护无代码实现 | [03-security-specification.md](./03-security-specification.md) | §4 PromptInjectionGuard 完整实现 |
| **M-01** | 日志规范完全缺失 | [06-operability-guide.md](./06-operability-guide.md) | §2 结构化日志规范(JSON 格式/字段/级别/采样) |
| **E-01** | 多租户架构设计空白 | [07-scalability-patterns.md](./07-scalability-patterns.md) | §2 完整多租户方案(RLS/配额/Onboarding) |

### 🟠 Major — Phase 1 结束前解决（11 项）

| 改进编号 | 问题 | 所在文档 | 章节 |
|---|---|---|---|
| **P-02** | 模型网关弹性参数不全(缺熔断状态机) | [05-performance-optimization.md](./05-performance-optimization.md) | §3 熔断器完整参数矩阵+状态机图 |
| **P-03** | RAG Pipeline 缺少并行化 | [05-performance-optimization.md](./05-performance-optimization.md) | §4 Query并行化+Embedding缓存+Rerank分层 |
| **P-04** | agent_run.tenant_id JSONB索引错误 | [04-data-design-complete.md](./04-data-design-complete.md) | §2 修正为独立列+普通复合索引 |
| **S-03** | 密钥管理方案空洞 | [03-security-specification.md](./03-security-specification.md) | §5 密钥分级/KMS方案/轮换流程 |
| **S-04** | 工具权限 DB 设计缺失 | [03-security-specification.md](./03-security-specification.md) | §7 tool_permission + tenant_tool_config 表DDL |
| **S-05** | 脱敏自动化缺失 | [03-security-specification.md](./03-security-specification.md) | §6 Pydantic SensitiveStr + Jackson Module + Logback Filter |
| **S-06** | mTLS vs Service Token 关系不清 | [03-security-specification.md](./03-security-specification.md) | §3 双轨制认证(生产mTLS+dev ST) |
| **M-02** | 数据库迁移策略缺失 | [04-data-design-complete.md](./04-data-design-complete.md) | §5 Flyway统一迁移/回滚策略 |
| **M-03** | 配置管理策略缺失 | [06-operability-guide.md](./06-operability-guide.md) | §3 配置层次/环境区分/敏感配置KMS |
| **M-05** | CI/CD 流水线定义空洞 | [06-operability-guide.md](./06-operability-guide.md) | §4 完整 CI pipeline(9个阶段) |
| **E-02** | Provider 抽象接口未标准化 | [07-scalability-patterns.md](./07-scalability-patterns.md) | §3 BaseLLMProvider ABC 定义+Checklist |

### 🟡 Minor — Phase 2 逐步完善（6 项）

| 改进编号 | 问题 | 所在文档 | 章节 |
|---|---|---|---|
| **P-05** | Step 批量写入策略缺失 | [05-performance-optimization.md](./05-performance-optimization.md) | §6 StepBuffer 内存攒批+定时flush |
| **C-05** | 工具注册 API 规范缺失 | [02-communication-contracts.md](./02-communication-contracts.md) | §5 动态工具注册 REST API(6个端点) |
| **M-04** | Feature Flag 能力缺失 | [06-operability-guide.md](./06-operability-guide.md) | §5 Unleash 配置示例(灰度/AB/紧急关闭) |
| **E-03** | Orchestrator 多实例状态共享 | [07-scalability-patterns.md](./07-scalability-patterns.md) | §4 Redis Checkpoint + HPA + Sticky Session |
| **E-04** | 工具动态注册机制 | [07-scalability-patterns.md](./07-scalability-patterns.md) | §5 三阶段演进(DB加载→热加载→沙箱执行) |
| **E-05** | API 契约测试机制 | [02-communication-contracts.md](./02-communication-contracts.md) | §6 CI契约测试(buf breaking+spectral+grpcurl) |

---

## 10. 详细设计入口

### 快速启动

→ **[quick-start.md](./quick-start.md)** — 开发环境快速启动指南，包含：
- 前置要求与工具安装
- 一键启动基础设施（Docker）
- 各服务启动命令（Python/Java/前端）
- 常用命令速查表
- 常见问题解答

### 开发工具

→ **[dev-jenv-guide.md](./dev-jenv-guide.md)** — jenv Java 版本管理指南，包含：
- jenv 工作原理与架构
- 安装配置步骤（macOS/Linux）
- 基本用法（安装、注册、切换版本）
- 进阶用法（别名、插件、项目级锁定）
- 常见问题与解决方案
- 与项目集成配置

### Agent 开发

→ **[agent-dev-guide.md](./agent-dev-guide.md)** — 新人上手 Agent 开发指南，包含：
- 核心概念（状态、节点、边、Checkpoint）
- 项目代码结构导览
- Agent 执行流程图解
- 状态定义与创建
- 开发新节点模板
- 开发新工具方法
- 测试指南（单元测试/集成测试）
- 调试技巧与常见问题

### 前端设计（v2.2 新增）

→ **[09-frontend-design.md](./09-frontend-design.md)** 包含：
- §2 技术选型（React 18 + TypeScript + Vite + Ant Design）
- §3 API 类型定义（与后端 Protobuf/OpenAPI 一致）
- §4 认证与权限（JWT + RBAC + 多租户）
- §5 SSE 流式通信（对话流式输出实现）
- §6 核心模块设计（对话界面、审批中心、工具管理）
- §7 监控面板（Dashboard 设计）
- §8 错误处理（错误码映射）
- §9 测试策略（单元测试 + E2E 测试）
- §10 部署配置（Docker + Nginx）

### 后端设计

以下为原 v1.0 方案的完整内容（3517 行），包含未被拆分到专题文档的章节：

→ **[08-main-technical-design.md](./08-main-technical-design.md)** 包含：
- §3 Service Mesh 完整方案(Istio YAML)
- §4.2 四类连接池配置详情
- §5-6 Token预算与成本优化
- §7 Monorepo 目录结构与服务依赖图
- §8 七大服务职责详细划分
- §9-10 通信规范与 API 版本治理
- §11 灾难恢复(RTO≤30min/RPO≤5min)
- §13 三类关键业务流程时序说明
- §14 生产红线与质量门槛
- §14.4 缓存三防(穿透/击穿/雪崩)完整代码
- §15 安全测试矩阵(OWASP Top 10+Fuzzing)
- §16 可观测性(Trace/Metrics/Logs三大支柱)
- §16.5 告警分级(P1-P4)+On-call轮值
- §17 Agent 三大设计模式(ReAct/PlanExecute/MultiAgent)
- §18 评测金字塔(GoldSet/LLM-Judge/CI融入)
- §19 场景选择矩阵
- §20 四阶段实施规划(含验收清单)
- §21 运维手册(启停/排查/回滚/巡检)
- §22 混沌工程(Chaos Mesh YAML + Game Day)
- §23 风险矩阵(技术/业务/组织)
- §24 术语表与参考资料
