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
| API 入口/工具 | Java 17/21 + Spring Boot 3.2 |
| 数据库 | PostgreSQL 16 + pgvector |
| 缓存/消息 | Redis 7 + Kafka 3.6 |
| 观测 | OpenTelemetry + Prometheus + Grafana |

> **Java 版本说明**：
> - gateway-java: Java 17（稳定版本，无虚拟线程需求）
> - tool-bus-java: Java 21（使用虚拟线程优化批量工具执行）
> - governance-java: Java 21

### 服务拓扑
```
Gateway (Java) → Orchestrator (Python) → Model Gateway (Python)
                      ↓
               Tool Bus (Java) → Governance (Java)
                      ↓
               Knowledge (Python)
```

### 服务端口

| 服务 | HTTP 端口 | gRPC 端口 | 说明 |
|------|----------|----------|------|
| Gateway | 8080 | 9091 | API 入口 |
| Orchestrator | 8000 | 50100 | Agent 编排（开发脚本使用 8001） |
| Model Gateway | 8002 | - | 模型统一网关 |
| Knowledge | 8003 | - | 知识库服务 |
| Tool Bus | 8083 | 40051 | 工具执行 |
| Governance | 8082 | - | 风控审批 |

---

## 代码组织

```
services/orchestrator-python/app/
├── api/          # 路由层 (FastAPI endpoints)
├── core/         # 配置、异常、常量
│   ├── token_counter.py      # [新增] Token 计数
│   ├── context_manager.py    # [新增] 上下文截断
│   ├── sensitive_filter.py   # [新增] 敏感信息脱敏
│   └── resilience.py         # [优化] 熔断器（线程安全）
├── graph/        # LangGraph 状态机
│   ├── nodes/    # 各节点实现
│   │   ├── thinking.py       # [优化] 集成上下文截断
│   │   └── tool_call.py      # [优化] 集成参数校验
│   ├── state.py  # 状态定义
│   └── builder.py # [优化] 动态并发限制
├── memory/       # 对话记忆
│   ├── long_term_memory.py   # [新增] 长时记忆（向量存储）
│   └── summary_generator.py  # [新增] 对话摘要生成
├── tools/        # 工具客户端
│   └── validators/
│       └── json_schema_validator.py  # [新增] JSON Schema 校验
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
    # 核心字段（完整定义见 services/orchestrator-python/app/graph/state.py）
    messages: Annotated[list, add_messages]  # 对话历史（自动累积）
    tool_calls: list[dict]          # 工具调用请求
    tool_results: list[dict]        # 工具执行结果
    current_step: str               # 当前步骤类型
    risk_level: str                 # low/medium/high/critical
    approval_id: str | None          # 审批单 ID（替代 needs_approval）
    approval_status: str | None      # pending/approved/rejected
    consecutive_errors: int          # 连续失败计数 (S-AGENT-11)
    step_count: int                  # 步骤计数器
    max_steps: int                   # 最大步骤限制
```

> 模式选择（ReAct/Plan-and-Execute/Multi-Agent）见 S-AGENT-09。节点模板见 `/langgraph-node`。

### 安全（项目特有）
- **五层鉴权**：RBAC → 租户隔离 → ABAC → 频率限制 → 风险等级（S-AGENT-06）
- **mTLS**：生产环境必须启用（配置见 `infra/k8s/istio-peer-authentication.yaml`）
- **审计表触发器**：`audit_event` 有触发器阻断删改
- **输入截断**：用户输入限制 8000 tokens（MAX_USER_INPUT_TOKENS）
- **输出泄露检测**：`output_guard.py` 实现 L4 层防御
- **[新增] 上下文截断**：`context_manager.py` 实现滑动窗口策略，防止 token 超限
- **[新增] 参数校验**：`json_schema_validator.py` 实现 JSON Schema 校验，防止恶意输入
- **[新增] 日志脱敏**：`sensitive_filter.py` 自动脱敏手机号/身份证/API Key

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
# Agent 执行配置
MAX_AGENT_STEPS = 10           # S-AGENT-10 步数上限
AGENT_TOTAL_TIMEOUT_S = 300    # Agent 总超时（5分钟）
MODEL_CALL_TIMEOUT_S = 30      # Provider 超时
TOOL_CALL_TIMEOUT_S = 15       # S-AGENT-08 工具超时
APPROVAL_WAIT_TIMEOUT_S = 7200 # 审批等待超时（2小时）

# Token 限制
MAX_USER_INPUT_TOKENS = 8000   # S-AGENT-03 输入限制
MAX_CONTEXT_WINDOW_TOKENS = 128000  # 模型上下文窗口
MAX_SYSTEM_PROMPT_TOKENS = 4000    # 系统提示词上限
CONTEXT_RESPONSE_RESERVED_TOKENS = 8000  # 响应预留 token

# 并发限制
MAX_CONCURRENT_REQUESTS = 50      # 最大并发请求数
MAX_CONCURRENT_MODEL_CALLS = 20   # 并发模型调用上限
MAX_CONCURRENT_TOOL_CALLS = 30    # 并发工具调用上限

# 熔断器配置
CIRCUIT_FAILURE_THRESHOLD = 5     # 熔断器失败阈值
CIRCUIT_RECOVERY_TIMEOUT = 30     # 熔断器恢复超时（秒）

# 重试配置
RETRY_MAX_ATTEMPTS = 3            # 最大重试次数
RETRY_MIN_WAIT = 1.0              # 最小等待时间（秒）
RETRY_MAX_WAIT = 10.0             # 最大等待时间（秒）

# 缓存配置
CACHE_LOCAL_MAXSIZE = 1000        # 本地缓存最大条数
CACHE_DEFAULT_TTL = 600           # 默认缓存 TTL（秒）
CACHE_RAG_TTL = 600               # RAG 结果缓存 TTL
CACHE_TOOL_SCHEMA_TTL = 3600      # 工具 Schema 缓存 TTL

# HTTP 连接池
HTTP_MAX_CONNECTIONS = 100        # HTTP 最大连接数
HTTP_MAX_KEEPALIVE = 20           # HTTP 最大 keepalive 连接数
HTTP_KEEPALIVE_EXPIRY = 30.0      # HTTP keepalive 过期时间（秒）

# OpenTelemetry
OTEL_ENABLED = True               # 是否启用 OTel
OTLP_ENDPOINT = "http://localhost:4317"  # OTLP gRPC 端点
```

---

## 生产级架构增强（2026-05-13）

本次优化解决了以下生产级差距：

| 维度 | 新增模块 | 解决问题 |
|------|----------|----------|
| **容错** | `resilience.py` 线程安全改造 | 多协程竞态导致熔断器状态混乱 |
| **上下文** | `token_counter.py` + `context_manager.py` | Token 超限导致模型调用失败 |
| **安全** | `json_schema_validator.py` | 恶意输入穿透到 ToolBus |
| **合规** | `sensitive_filter.py` | 日志泄露敏感信息 |
| **记忆** | `long_term_memory.py` + `summary_generator.py` | 无法支持跨会话对话 |
| **配置** | `builder.py` + `qwen.py` | 硬编码值导致运维困难 |

**关键变更**：
- 熔断器添加 `asyncio.Lock` 保护状态转换
- thinking 节点集成上下文截断策略
- tool_call 节点集成 JSON Schema 参数校验
- 并发限制从配置动态读取

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
