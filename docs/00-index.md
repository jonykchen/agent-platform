# Agent Platform 文档索引

> **版本**：v3.0 | **状态**：开发中 | **更新**：2026-05-13

本文档为技术方案的总览索引。项目采用 **Python 编排 + Java 核心服务 + 国内 LLM** 混合架构。

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

## 9. 文档索引

| 文档 | 内容 |
|------|------|
| [quick-start.md](./quick-start.md) | 快速启动指南 |
| [agent-dev-guide.md](./agent-dev-guide.md) | Agent 开发指南 |
| [dev-jenv-guide.md](./dev-jenv-guide.md) | jenv 工具配置 |
| [01-engineering-standards.md](./01-engineering-standards.md) | 工程规范 |
| [02-communication-contracts.md](./02-communication-contracts.md) | 通信契约 |
| [03-security-specification.md](./03-security-specification.md) | 安全规范 |
| [04-data-design-complete.md](./04-data-design-complete.md) | 数据设计 |
| [05-performance-optimization.md](./05-performance-optimization.md) | 性能优化 |
| [06-operability-guide.md](./06-operability-guide.md) | 运维指南 |
| [07-scalability-patterns.md](./07-scalability-patterns.md) | 扩展性设计 |
| [09-frontend-design.md](./09-frontend-design.md) | 前端设计 |
| [14-testing-strategy.md](./14-testing-strategy.md) | 测试体系与质量保障 |
