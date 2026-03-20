---
name: tech_decisions
description: 关键技术选型和架构决策记录
type: project
---

# 技术决策记录

## ADR-001: 混合语言架构

**决策**: 采用 Python 编排 + Java 核心服务的混合架构

**Why**:
- Python 是 AI/LLM 生态的主场，LangGraph、Pydantic 等工具链成熟
- Java 是企业级服务的稳定性主场，Spring Boot 生态完善
- 通过 gRPC 通信，语言无关，便于团队分工

**How to apply**:
- Agent 相关逻辑全部放在 Python 服务 (orchestrator, model-gateway, knowledge)
- 业务逻辑、风控、审计放在 Java 服务 (gateway, tool-bus, governance)
- 接口契约用 Proto 定义，统一生成代码

---

## ADR-002: LangGraph 作为 Agent 编排框架

**决策**: 使用 LangGraph 而非纯 LangChain

**Why**:
- LangGraph 提供显式的状态机模型，适合复杂多步 Agent
- Checkpoint 机制支持暂停/恢复，符合审批场景需求
- 更好的可观测性和调试能力

**How to apply**:
- 所有 Agent 流程用 LangGraph Graph 定义
- 状态用 TypedDict 明确类型
- 每个节点是独立函数，便于测试

---

## ADR-003: 国内 LLM 为主

**决策**: 优先接入国内 LLM (通义千问、GLM、Kimi、DeepSeek)

**Why**:
- 企业客户数据合规要求
- 国内网络环境稳定性
- 成本可控

**How to apply**:
- Model Gateway 统一封装，屏蔽厂商差异
- 预留 OpenAI 接口用于测试/对比
- 路由策略可配置，支持灰度

---

## ADR-004: PostgreSQL + pgvector 起步

**决策**: 初期使用 pgvector 做向量检索，规模超 150 万再迁移 Qdrant

**Why**:
- 减少运维复杂度，一个数据库解决所有需求
- pgvector 0.7+ 性能已能满足 MVP 阶段
- 迁移路径清晰，无需早期过度设计

**How to apply**:
- knowledge-python 服务抽象向量存储接口
- 预留 Qdrant 适配器，随时可切换
- 监控向量表大小，提前预警
