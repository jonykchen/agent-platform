# Agent Platform — Claude 项目配置

> 此文件为 Claude Code 提供项目上下文和开发指导

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

## 开发规范

### 代码组织
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

### 命名约定
| 标识符 | 用途 | 示例 |
|--------|------|------|
| `request_id` | 全链路追踪 | `req_abc123` |
| `tenant_id` | 租户隔离 | `tenant_001` |
| `run_id` | Agent 执行标识 | `run_xyz789` |
| 工具命名 | `verb_noun` | `query_order_status` |

### 质量门槛
| 指标 | 目标 |
|------|------|
| JSON 合法率 | ≥ 99.5% |
| 工具调用成功率 | ≥ 98% |
| 简单问答 P95 | < 6s |
| 单工具任务 P95 | < 15s |

### 并行开发效率
**多任务并行执行，单次响应最大化利用。**

| 场景 | 策略 |
|------|------|
| 多个独立任务 | 单条消息并行调用多个工具，避免串行等待 |
| 多文件读取/搜索 | 并行发起 Glob、Grep、Read |
| 研究 + 实现 | 后台启动 Explore Agent，前台继续分析 |

**执行原则：**
1. 识别任务依赖关系，无依赖则并行
2. 单条消息内发起所有独立工具调用
3. 避免为并行任务逐个确认，批量执行

### 测试驱动开发 (TDD)
**先写测试，后写实现。**

| 任务类型 | 流程 |
|---------|------|
| Bug 修复 | 复现测试 → 修复 → 验证通过 |
| 新功能 | 失败测试 → 最小实现 → 重构 |
| 重构 | 确保测试覆盖 → 重构 → 测试通过 |

**强制要求**: 功能提交必须包含对应测试

### 变更最小化
**只改必须改的，不碰无关代码。**

- 不修改相邻代码格式/注释
- 不删除预先存在的"死代码"
- 匹配现有代码风格
- 发现无关问题时仅提示，不主动修复

### 错误处理策略
| 层级 | 处理方式 |
|------|---------|
| 外部 API | 完整异常处理 + 重试 + 超时 |
| 内部服务调用 | 异常传播 + 日志 |
| 私有函数 | 前置断言，无过度防御 |
| 不可能分支 | 不处理，让失败显式暴露 |

### 代码自检清单
提交前自动检查：
- 无硬编码密钥/密码
- 无裸 `except:` 捕获
- 敏感信息已脱敏
- 新增配置有默认值
- 破坏性变更有迁移脚本

---

## Agent 开发模式

### 状态机设计 (LangGraph)
```python
from typing import TypedDict

class AgentState(TypedDict):
    messages: list[dict]
    tool_calls: list[dict]
    current_step: str
    risk_level: str  # low/medium/high/critical
    needs_approval: bool
    errors: list[str]
```

### 节点实现模板
```python
async def xxx_node(state: AgentState) -> dict:
    """节点说明"""
    log.info("xxx_node started", run_id=state["run_id"])
    
    try:
        result = await _process(state)
        return {"key": result}
    except Exception as e:
        log.error("xxx_node failed", error=str(e))
        raise
```

### 工具调用模式选择
| 模式 | 适用场景 |
|------|---------|
| ReAct | 单工具、简单推理 |
| Plan-and-Execute | 多步骤、复杂规划 |
| Multi-Agent | 跨域协作 |

---

## 安全红线

### 必须遵守
1. **审计表不可删改**: `audit_event` 有触发器阻断
2. **敏感信息脱敏**: 手机号/身份证/API Key 必须过滤
3. **工具调用鉴权**: 五层检查 (RBAC→租户→ABAC→频率→风险)
4. **mTLS 双向认证**: 生产环境必须启用

### 禁止行为
- ❌ 硬编码密钥/密码
- ❌ 日志输出原始用户输入 (>500字符)
- ❌ 跳过风控执行高风险工具
- ❌ 提交 .env 或密钥文件

---

## Prompt 注入防护

### 六层防御
| 层级 | 措施 |
|------|------|
| L1 | 输入长度限制 ≤ 8000 tokens |
| L2 | 已知注入模式检测 |
| L3 | 结构化包装 `<user_message>...</user_message>` |
| L4 | 输出泄露检测 |
| L5 | 二次校验分类器 |
| L6 | 沙箱执行 |

### 已知注入模式
```
英文: ignore previous instructions, you are now a...
中文: 忽略以上指令, 你现在是一个...
```

---

## 错误处理体系

```python
BasePlatformException
├── InvalidRequestError (10xxx)    # 请求错误
├── UnauthorizedError (10xxx)      # 认证失败
├── RateLimitedError (10xxx)       # 限流
├── AgentError (20xxx)
│   ├── MaxStepsExceededError      # 步骤超限
│   ├── ContextTooLongError        # 上下文过长
│   └── ToolNotFoundError          # 工具不存在
├── ModelGatewayError (30xxx)
│   ├── AllProvidersDownError      # 全挂
│   └── ContentFilteredError       # 内容过滤
└── ToolBusError (40xxx)
    ├── ToolValidationError        # 参数校验失败
    ├── ToolExecutionFailedError   # 执行失败
    └── ApprovalRequiredError      # 需审批
```

---

## 常用命令

```bash
# 开发环境
make dev              # 启动基础设施
make dev-down         # 停止

# 代码质量
make lint             # Lint 检查
make fmt              # 格式化
make test             # 运行测试
make ci               # 完整 CI

# Proto
make proto            # 生成代码
buf lint contracts/proto

# 单服务
cd services/orchestrator-python
uv run pytest tests/ -v --cov=app

# 数据库
psql -h localhost -U app_user -d agent_platform
```

---

## 开发流程

### 功能开发
```
1. 创建分支: git checkout -b feature/xxx
2. 开发实现: 遵循 TDD
3. 本地验证: make ci
4. 提交代码: git commit -m "feat(scope): xxx"
5. 创建 PR: gh pr create
6. 等待 Review 和 CI
7. 合并到 master
```

### 提交规范
```
feat(scope): 新功能
fix(scope): Bug 修复
refactor(scope): 重构
docs: 文档
test(scope): 测试
perf(scope): 性能优化
```

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [工程规范](docs/01-engineering-standards.md) | 代码结构、日志规范 |
| [通信契约](docs/02-communication-contracts.md) | API、错误码 |
| [安全规范](docs/03-security-specification.md) | 审计、密钥、权限 |
| [数据设计](docs/04-data-design-complete.md) | 表结构、索引 |
| [性能优化](docs/05-performance-optimization.md) | 缓存、并行化 |
| [运维指南](docs/06-operability-guide.md) | 部署、监控 |
| [扩展性设计](docs/07-scalability-patterns.md) | 多租户、灰度 |

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

### 关键配置
```python
MAX_AGENT_STEPS = 10           # 最大循环次数
MODEL_CALL_TIMEOUT_S = 30      # 模型超时
TOOL_CALL_TIMEOUT_S = 15       # 工具超时
MAX_USER_INPUT_TOKENS = 8000   # 输入限制
```
