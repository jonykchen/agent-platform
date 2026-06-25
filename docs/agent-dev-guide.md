# Agent 开发指南

> 本指南帮助新人快速上手 Agent 开发，理解核心概念和代码结构

---

## 1. 核心概念

### 1.1 Agent 是什么？

Agent 是一个**状态机**，通过**推理-行动循环**完成复杂任务：

```
用户输入 → 推理(thinking) → 决策 → 执行(tool_call) → 观察结果 → 继续推理 → 最终回答
```

本项目采用 **ReAct 模式**（Reasoning + Acting），使用 **LangGraph** 实现状态机。

### 1.2 关键术语

| 术语 | 说明 |
|------|------|
| **State** | Agent 的当前状态，包含对话历史、工具调用、错误等 |
| **Node** | 状态机中的一个处理节点，执行特定逻辑 |
| **Edge** | 节点之间的连接，决定流转方向 |
| **Checkpoint** | 状态持久化，用于暂停恢复 |
| **Interrupt** | 在特定节点暂停执行，等待外部输入（如审批） |

---

## 2. 项目结构

```
services/orchestrator-python/app/
├── graph/                  # 状态机核心
│   ├── state.py            # AgentState 状态定义 ★ 入口
│   ├── builder.py          # 图构建、节点连接 ★ 核心
│   └── nodes/              # 各节点实现
│       ├── thinking.py     # 推理节点
│       ├── tool_call.py    # 工具调用节点
│       ├── risk_check.py   # 风控检查节点
│       ├── approval_wait.py # 审批等待节点
│       └── final_answer.py # 最终回答节点
├── tools/                  # 工具客户端
│   └── clients/
│       ├── tool_bus_client.py    # ToolBus gRPC 客户端
│       └── model_gateway_client.py # Model Gateway 客户端
├── memory/                 # 状态持久化
│   ├── session_store.py    # 会话存储
│   ├── checkpoint_store.py # Checkpoint 存储
│   └── kafka_callback.py   # Kafka 回调恢复
├── core/                   # 基础设施
│   ├── config.py           # 配置管理
│   ├── exceptions.py       # 异常定义
│   ├── constants.py        # 常量
│   └── prompt_guard.py     # Prompt 注入防护
└── api/                    # API 层
    └── v1/chat.py          # 对话接口
```

---

## 3. Agent 执行流程

### 3.1 流程图

```
START → thinking → [决策]
                     │
        ┌────────────┼────────────┐
        │            │            │
   [工具调用]    [直接回答]    [错误/超限]
        │            │            │
        ▼            ▼            ▼
    risk_check   final_answer  final_answer
        │
   ┌────┼────┐
   │    │    │
[低风险] [高风险] [拒绝]
   │    │    │
   ▼    ▼    ▼
tool_call  approval_wait  final_answer
   │         │
   │    [审批结果]
   │    ┌────┼────┐
   │    │    │    │
   │ [通过] [拒绝]
   │    │    │
   │    ▼    ▼
   │ tool_call  final_answer
   │    │
   └────┴────→ thinking (循环)
                │
                ▼
           final_answer → END
```

### 3.2 节点职责

| 节点 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **thinking** | 模型推理，决定下一步 | 用户输入、工具结果 | current_step, tool_calls |
| **risk_check** | 评估风险等级 | tool_calls | risk_level, approval_required |
| **tool_call** | 执行工具调用 | tool_calls | tool_results |
| **approval_wait** | 等待审批（interrupt） | approval_id | approval_status |
| **final_answer** | 生成最终响应 | 所有状态 | output |

---

## 4. 状态定义

`AgentState` 是 Agent 的核心数据结构，所有节点共享：

```python
# services/orchestrator-python/app/graph/state.py

class AgentState(TypedDict):
    """Agent 状态"""

    # 对话历史（自动累积）
    messages: Annotated[list, add_messages]

    # 当前输入
    input: str

    # 会话信息
    session_id: str
    tenant_id: str
    user_id: str
    request_id: str

    # 执行状态
    step_count: int          # 当前步骤数
    max_steps: int           # 最大步骤限制
    current_step: str        # 下一步类型

    # 工具调用
    tool_calls: list[dict]   # 待执行的工具调用
    tool_results: list[dict] # 工具执行结果

    # 风险检查
    risk_level: str          # low/medium/high/critical
    risk_reason: str | None

    # 审批信息
    approval_id: str | None
    approval_status: str | None  # pending/approved/rejected

    # 最终输出
    output: str
    error: str | None
    error_code: str | None

    # 元数据
    metadata: dict
```

### 创建初始状态

```python
from app.graph.state import create_initial_state

state = create_initial_state(
    input="查询订单 ORD-12345 的状态",
    session_id="session_abc",
    tenant_id="tenant_001",
    user_id="user_001",
    request_id="req_xyz",
    max_steps=10,
)
```

---

## 5. 开发新节点

### 5.1 节点模板

每个节点是一个异步函数，接收状态，返回更新字典：

```python
# services/orchestrator-python/app/graph/nodes/xxx_node.py

import structlog
from app.graph.state import AgentState

logger = structlog.get_logger()


async def xxx_node(state: AgentState) -> dict:
    """节点说明
    
    Args:
        state: 当前 Agent 状态
    
    Returns:
        状态更新字典（部分字段）
    """
    request_id = state["request_id"]
    
    logger.info("node_started", node="xxx", request_id=request_id)
    
    try:
        # 1. 读取输入状态
        input_value = state.get("input")
        
        # 2. 执行核心逻辑
        result = await _process(input_value)
        
        # 3. 返回状态更新
        logger.info("node_completed", node="xxx", request_id=request_id)
        
        return {
            "current_step": "next_node",
            "output_field": result,
        }
        
    except Exception as e:
        logger.error("node_failed", node="xxx", error=str(e))
        return {
            "error": str(e),
            "error_code": "ERR_XXX",
        }


async def _process(input_value: str) -> dict:
    """核心处理逻辑"""
    # 实现具体业务逻辑
    return {"result": "processed"}
```

### 5.2 注册节点

在 `builder.py` 中添加节点和边：

```python
# services/orchestrator-python/app/graph/builder.py

from app.graph.nodes.xxx_node import xxx_node

def build_agent_graph():
    graph = StateGraph(AgentState)
    
    # 添加节点
    graph.add_node("xxx", xxx_node)
    
    # 添加边（连接到其他节点）
    graph.add_edge("xxx", "next_node")
    
    # 或添加条件边
    graph.add_conditional_edges(
        "xxx",
        route_after_xxx,
        {
            "path_a": "node_a",
            "path_b": "node_b",
        },
    )
    
    return graph.compile()
```

### 5.3 路由函数

条件边需要路由函数决定下一步：

```python
def route_after_xxx(state: AgentState) -> str:
    """xxx 后的路由决策"""
    
    # 检查状态字段
    if state.get("error"):
        return "error"
    
    current_step = state.get("current_step")
    
    if current_step == "path_a":
        return "path_a"
    
    return "path_b"
```

---

## 6. 开发新工具

### 6.1 工具注册

工具在 **ToolBus (Java)** 服务注册，通过 gRPC 调用。

工具定义字段：

```json
{
  "name": "query_order_status",
  "version": "1.0",
  "category": "query",
  "description": "查询订单状态",
  "input_schema": {
    "type": "object",
    "properties": {
      "order_id": {"type": "string"}
    },
    "required": ["order_id"]
  },
  "risk_level": "low",
  "requires_approval": false
}
```

### 6.2 在 Python 中调用工具

通过 `ToolBusClient` 调用：

```python
from app.tools.clients.tool_bus_client import ToolBusClient

client = ToolBusClient()

result = await client.execute_tool(
    tool_name="query_order_status",
    arguments={"order_id": "ORD-12345"},
    context={
        "request_id": "req_xyz",
        "tenant_id": "tenant_001",
        "user_id": "user_001",
    },
)

# result 结构
{
    "call_id": "call_abc",
    "status": "success",  # success/pending_approval/rejected/failed
    "result_json": '{"status": "已发货"}',
    "risk_level": "low",
    "approval_id": null,  # 需要审批时有值
}
```

### 6.3 Mock 工具（开发测试）

在 `tool_call.py` 中添加 Mock 实现：

```python
async def _mock_execute_tool(tool_name: str, arguments: dict) -> dict:
    """Mock 工具执行"""
    
    if tool_name == "my_new_tool":
        return {
            "call_id": "call_mock",
            "status": "success",
            "result_json": json.dumps({"data": "mock_result"}),
            "risk_level": "low",
        }
    
    # 其他工具...
```

---

## 7. 测试指南

### 7.1 单元测试

```python
# tests/unit/test_xxx_node.py

import pytest
from app.graph.nodes.xxx_node import xxx_node
from app.graph.state import create_initial_state


@pytest.mark.asyncio
async def test_xxx_node_success():
    """测试正常执行"""
    state = create_initial_state(
        input="test input",
        session_id="test_session",
        tenant_id="test_tenant",
        user_id="test_user",
        request_id="test_request",
    )
    
    result = await xxx_node(state)
    
    assert result.get("error") is None
    assert result.get("current_step") == "expected_step"


@pytest.mark.asyncio
async def test_xxx_node_error():
    """测试错误处理"""
    state = create_initial_state(...)
    state["input"] = ""  # 触发错误
    
    result = await xxx_node(state)
    
    assert result.get("error") is not None
    assert result.get("error_code") == "ERR_XXX"
```

### 7.2 集成测试

```python
# tests/integration/test_agent_flow.py

import pytest
from app.graph.builder import build_agent_graph
from app.graph.state import create_initial_state


@pytest.mark.asyncio
async def test_agent_query_flow():
    """测试完整查询流程"""
    graph = build_agent_graph()
    
    state = create_initial_state(
        input="查询订单 ORD-12345",
        session_id="test",
        tenant_id="tenant_001",
        user_id="user_001",
        request_id="req_test",
    )
    
    # 执行 Agent
    result = await graph.invoke(state)
    
    # 验证结果
    assert result.get("output") is not None
    assert result.get("error") is None
```

### 7.3 运行测试

```bash
cd services/orchestrator-python

# 运行所有测试
uv run pytest tests/ -v

# 运行单个测试
uv run pytest tests/unit/test_xxx_node.py -v

# 运行带覆盖率
uv run pytest tests/ -v --cov=app
```

---

## 8. 调试技巧

### 8.1 日志查看

使用结构化日志，关键字搜索：

```bash
# 查看节点执行日志
grep "node_started" logs/app.log
grep "node_completed" logs/app.log

# 查看路由决策
grep "route_decision" logs/app.log

# 按 request_id 查询完整链路
grep "req_xyz" logs/app.log
```

### 8.2 状态检查

在节点中打印状态：

```python
logger.debug("state_dump", state=dict(state))
```

### 8.3 本地调试

```python
# 在节点中打断点
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

---

## 9. 常见问题

### Q: 如何限制最大循环次数？

A: 在 `AgentState` 中设置 `max_steps`，`thinking_node` 会检查：

```python
if step_count >= max_steps:
    return {"error": "超过最大步骤数"}
```

### Q: 如何实现审批暂停？

A: 使用 `interrupt_before`：

```python
graph.compile(
    checkpointer=MemorySaver(),
    interrupt_before=["approval_wait"],
)
```

Agent 在 `approval_wait` 前暂停，等待 Kafka 回调恢复。

### Q: 如何添加新字段到状态？

A: 在 `state.py` 中添加字段，然后更新所有使用该字段的节点。

### Q: 工具调用失败怎么办？

A: `tool_call_node` 会：
1. 记录错误到 `tool_results`
2. 如果所有工具失败，返回 `error`
3. 如果部分成功，继续推理循环

---

## 10. 参考资源

| 资源 | 说明 |
|------|------|
| [LangGraph 文档](https://langchain-ai.github.io/langgraph/) | 状态机框架官方文档 |
| [01-engineering-standards.md](./01-engineering-standards.md) | 工程规范 |
| [02-communication-contracts.md](./02-communication-contracts.md) | 工具注册 API |
| [03-security-specification.md](./03-security-specification.md) | 风控规则 |
| [05-performance-optimization.md](./05-performance-optimization.md) | 性能优化 |
| [09-frontend-design.md](./09-frontend-design.md) | 前端设计（✅ 已实施） |

---

## 11. 前端模块

> 前端代码位于 `services/web-frontend/`，实现状态：**已实施**

### 11.1 前端功能一览

| 模块 | 功能 | 状态 |
|------|------|------|
| 对话界面 | SSE 流式、虚拟滚动、离线队列 | 🔧 |
| 审批中心 | 列表、详情、WebSocket 通知 | 🔧 |
| 工具管理 | 注册、启用/禁用、详情 | 🔧 |
| 知识库管理 | 文档上传、索引状态、分块查看 | 🔧 |
| 审计日志 | 筛选、导出 CSV/JSON | 🔧 |
| 监控面板 | ECharts 图表、实时告警 | 🔧 |
| 用户管理 | CRUD、角色分配 | 🔧 |
| 租户配置 | 配额查看、设置修改 | 🔧 |
| 通知中心 | 实时通知、已读标记 | 🔧 |

### 11.2 前端目录结构

```
services/web-frontend/src/
├── routes/          # 16 个路由页面
│   ├── chat/        # 对话界面
│   ├── approval/    # 审批中心
│   ├── tools/       # 工具管理
│   ├── knowledge/   # 知识库管理
│   ├── audit/       # 审计日志
│   ├── dashboard/   # 监控面板
│   ├── users/       # 用户管理
│   ├── tenant/      # 租户配置
│   └── notifications/ # 通知中心
├── components/      # 共享组件
│   ├── chat/        # MessageList、InputBox、StepVisualizer
│   ├── approval/    # ApprovalCard、ApprovalTimeline
│   ├── knowledge/   # DocumentCard、DocumentUploader
│   ├── ui/          # FileUpload、KeyboardShortcuts
│   └── layout/      # Header、Sidebar、PageLayout
├── hooks/           # 7 个自定义 Hooks
│   ├── useChat.ts   # SSE 流式 + 离线队列
│   ├── useSSE.ts    # POST + 认证头 + 断线重连
│   └── useWebSocket.ts # 心跳 + 指数退避
├── stores/          # Zustand 状态
│   ├── authStore.ts # JWT 加密存储
│   └── chatStore.ts # 离线消息持久化
├── services/        # 12 个 API 服务层
└── types/           # 10 个类型定义
```

### 11.3 前端开发命令

```bash
cd services/web-frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 运行单元测试
npm run test

# 运行 E2E 测试
npm run test:e2e
```

---

## 附录：完整示例

### 示例：添加 RAG 检索节点

```python
# app/graph/nodes/rag_retrieve.py

import structlog
from app.graph.state import AgentState
from app.tools.clients.knowledge_client import KnowledgeClient

logger = structlog.get_logger()


async def rag_retrieve_node(state: AgentState) -> dict:
    """RAG 检索节点
    
    从知识库检索相关文档，支持后续回答。
    """
    request_id = state["request_id"]
    user_input = state["input"]
    
    logger.info("node_started", node="rag_retrieve", request_id=request_id)
    
    try:
        # 调用知识库服务
        client = KnowledgeClient()
        docs = await client.search(
            query=user_input,
            tenant_id=state["tenant_id"],
            top_k=10,
        )
        
        logger.info(
            "node_completed",
            node="rag_retrieve",
            doc_count=len(docs),
            request_id=request_id,
        )
        
        return {
            "current_step": "thinking",  # 返回推理节点
            "retrieved_docs": docs,
            "step_count": state["step_count"] + 1,
        }
        
    except Exception as e:
        logger.error("rag_failed", error=str(e), request_id=request_id)
        return {
            "error": str(e),
            "error_code": "ERR_RAG_FAILED",
        }


# 在 builder.py 中注册
graph.add_node("rag_retrieve", rag_retrieve_node)

# 在 thinking 后添加路由
if current_step == "rag_retrieve":
    return "rag_retrieve"
```