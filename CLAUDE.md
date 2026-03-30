# Agent Platform — 项目级配置

> 继承全局规则（~/.claude/CLAUDE.md），Agent/LLM 规则见 rules/agent-llm.md（S-AGENT-*），DevOps 规则见 rules/devops-infra.md（S-INFRA-*）。
> 本文档只记录项目特有上下文，通用规则不再重复。

---

## 项目概览

企业级 Agent 平台，采用 **Python 编排 + Java 核心服务 + 国内 LLM** 混合架构。

### 技术栈
| 层级 | 技术 |
|------|------|
| Agent 编排 | Python 3.12 + FastAPI + LangGraph + Pydantic V2 |
| 模型网关 | Python 3.12 + FastAPI + httpx |
| API 入口/工具 | Java 21 + Spring Boot 3.2 |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存/消息 | Redis 7 + Kafka 3.6 |
| 观测 | OpenTelemetry + Prometheus + Grafana |

### 服务拓扑
```
Gateway (Java) → Orchestrator (Python) → Model Gateway (Python)
                      ↓
               Tool Bus (Java) → Governance (Java)
                      ↓
               Knowledge (Python)
```

---

## 代码组织

```
services/orchestrator-python/app/
├── api/          # 路由层 (FastAPI endpoints)
├── core/         # 配置、异常、常量
├── graph/        # LangGraph 状态机
│   ├── nodes/    # 各节点实现
│   ├── state.py  # 状态定义
│   └── builder.py # 图构建
├── memory/       # 对话记忆
├── tools/        # 工具客户端
├── schemas/      # Pydantic 模型
└── prompts/      # Prompt 模板
```

## 命名约定

| 标识符 | 用途 | 示例 |
|--------|------|------|
| `request_id` | 全链路追踪 | `req_abc123` |
| `tenant_id` | 租户隔离 | `tenant_001` |
| `run_id` | Agent 执行标识 | `run_xyz789` |
| 工具命名 | `verb_noun` | `query_order_status` |

## 质量门槛

| 指标 | 目标 |
|------|------|
| JSON 合法率 | ≥ 99.5% |
| 工具调用成功率 | ≥ 98% |
| 简单问答 P95 | < 6s |
| 单工具任务 P95 | < 15s |

---

## Agent 架构（项目特有实现）

### 状态机 (LangGraph)
```python
class AgentState(TypedDict):
    messages: list[dict]
    tool_calls: list[dict]
    current_step: str
    risk_level: str       # low/medium/high/critical
    needs_approval: bool
    errors: list[str]
```

> 模式选择（ReAct/Plan-and-Execute/Multi-Agent）见 S-AGENT-09。节点模板见 `/langgraph-node`。

### 安全（项目特有）
- **五层鉴权**：RBAC → 租户隔离 → ABAC → 频率限制 → 风险等级（S-AGENT-06）
- **mTLS**：生产环境必须启用
- **审计表触发器**：`audit_event` 有触发器阻断删改
- **输入截断**：原始用户输入 > 500 字符截断

> 通用安全见 G-SEC-*，Prompt 注入防护见 S-AGENT-01~05。

---

## 错误码体系

```python
BasePlatformException
├── InvalidRequestError (10xxx)
├── UnauthorizedError (10xxx)
├── RateLimitedError (10xxx)
├── AgentError (20xxx)
│   ├── MaxStepsExceededError
│   ├── ContextTooLongError
│   └── ToolNotFoundError
├── ModelGatewayError (30xxx)
│   ├── AllProvidersDownError
│   └── ContentFilteredError
└── ToolBusError (40xxx)
    ├── ToolValidationError
    ├── ToolExecutionFailedError
    └── ApprovalRequiredError
```

---

## 关键配置值

```python
MAX_AGENT_STEPS = 10           # S-AGENT-10 步数上限
MODEL_CALL_TIMEOUT_S = 30      # Provider 超时
TOOL_CALL_TIMEOUT_S = 15       # S-AGENT-08 工具超时
MAX_USER_INPUT_TOKENS = 8000   # S-AGENT-03 输入限制
```

---

## 常用命令

```bash
make dev              # 启动基础设施
make dev-down         # 停止
make lint             # Lint 检查
make fmt              # 格式化
make test             # 运行测试
make ci               # 完整 CI
make proto            # 生成 Proto 代码
```

> 详细命令见 `.claude/commands.md`。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [文档索引](docs/00-index.md) | 总览、架构、技术选型 |
| [快速启动](docs/quick-start.md) | 开发环境配置 |
| [工程规范](docs/01-engineering-standards.md) | 代码结构、日志规范 |
| [通信契约](docs/02-communication-contracts.md) | API、错误码 |
| [安全规范](docs/03-security-specification.md) | 审计、密钥、权限 |
| [数据设计](docs/04-data-design-complete.md) | 表结构、索引 |
| [性能优化](docs/05-performance-optimization.md) | 缓存、并行化 |
| [运维指南](docs/06-operability-guide.md) | 部署、监控 |
| [扩展性设计](docs/07-scalability-patterns.md) | 多租户、灰度 |
| [前端设计](docs/09-frontend-design.md) | React UI 设计 |

---

## 快速参考

### 日志格式 (JSON)
```json
{
  "timestamp": "2026-05-09T10:30:00Z",
  "level": "INFO",
  "request_id": "req_abc",
  "tenant_id": "tenant_001",
  "service": "orchestrator",
  "message": "Node completed"
}
```

### 响应格式
```json
{
  "error": "ERR_CODE",
  "message": "技术信息",
  "user_message": "用户友好信息",
  "request_id": "req_abc"
}
```
