"""工具模块 - Agent 与外部系统交互桥梁

【模块架构】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ┌─────────────────────────────────┐
                    │         Agent Orchestrator       │
                    │      (LangGraph State Machine)  │
                    └─────────────────┬───────────────┘
                                      │ tool_calls
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TOOLS MODULE                                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         registry (注册表)                            │   │
│  │  • 工具注册与发现                                                     │   │
│  │  • 按类别/风险等级过滤                                               │   │
│  │  • 工具生命周期管理                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│              ┌───────────────────────┼───────────────────────┐              │
│              │                       │                       │              │
│              ▼                       ▼                       ▼              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐        │
│  │      base       │     │    clients      │     │   validators    │        │
│  │   工具基类      │     │   工具客户端     │     │   参数校验器     │        │
│  │  ToolProtocol   │     │  ToolBusClient  │     │ JSONSchema      │        │
│  │   BaseTool      │     │ ModelGateway    │     │   Validator     │        │
│  │   ToolResult    │     │    Client       │     │                 │        │
│  │ ToolMetadata    │     │                 │     │                 │        │
│  │   RiskLevel     │     │                 │     │                 │        │
│  │ ToolCategory    │     │                 │     │                 │        │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘        │
│              │                       │                       │              │
│              ▼                       ▼                       ▼              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐        │
│  │ 本地工具实现    │     │ ToolBus gRPC    │     │ 参数校验逻辑     │        │
│  │  (可选)        │     │    远程调用      │     │ defaults 填充   │        │
│  │                │     │                 │     │ type 检查       │        │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘        │
│                                  │                                         │
│                                  ▼                                         │
│                    ┌─────────────────────────────────┐                      │
│                    │     ToolBus Service (Java)      │                      │
│                    │   工具执行 + 风控审批 + 审计     │                      │
│                    └─────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘

【子模块职责】
┌────────────────────┬──────────────────────────────────────────────────────────────┐
│ 子模块              │ 职责描述                                                      │
├────────────────────┼──────────────────────────────────────────────────────────────┤
│ base               │ 工具抽象层：ToolProtocol（接口）、BaseTool（基类）、          │
│                    │ ToolResult（结果）、ToolMetadata（元信息）、RiskLevel/Category│
│ registry           │ 工具注册表：注册、发现、过滤、生命周期管理                      │
│ clients            │ 工具客户端：ToolBus gRPC 客户端、ModelGateway HTTP 客户端      │
│ validators         │ 参数校验器：JSON Schema 校验，防止恶意输入                      │
└────────────────────┴──────────────────────────────────────────────────────────────┘

【核心组件】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. base - 工具抽象层
   - ToolProtocol: 定义工具接口（Protocol 模式，零继承开销）
   - BaseTool: 提供通用实现（ABC 模式，支持运行时检查）
   - ToolResult: 标准化输出格式（success/data/error/metadata）
   - RiskLevel: 风险等级（LOW/MEDIUM/HIGH/CRITICAL）
   - ToolCategory: 工具类别（QUERY/ACTION/SYSTEM/INTEGRATION）

2. registry - 工具注册中心
   - 单例模式管理所有工具
   - 支持按类别、风险等级、标签过滤
   - 提供 FastAPI Depends 集成

3. clients - 外部服务客户端
   - ToolBusClient: gRPC 客户端，调用 Java ToolBus 服务
   - ModelGatewayClient: HTTP 客户端，调用模型网关

4. validators - 参数校验
   - JSONSchemaValidator: 基于 jsonschema 库实现完整 Draft-07 支持
   - 支持 defaults 填充、type 检查、required 校验

【工具命名规范】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

格式: verb_noun（动词_名词）

┌────────────────────┬──────────────────────────────────────────────────────────────┐
│ 类别                │ 示例                                                          │
├────────────────────┼──────────────────────────────────────────────────────────────┤
│ QUERY (查询类)      │ query_order_status, get_user_info, search_products            │
│ ACTION (动作类)     │ create_order, update_user_profile, execute_payment            │
│ SYSTEM (系统类)     │ get_system_health, clear_cache, restart_service               │
│ INTEGRATION (集成)  │ send_email, notify_webhook, sync_external_data                │
└────────────────────┴──────────────────────────────────────────────────────────────┘

【使用示例】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# 1. 定义工具（继承 BaseTool）
from app.tools import BaseTool, ToolResult, ToolMetadata, RiskLevel, ToolCategory

class QueryOrderTool(BaseTool):
    def _build_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="query_order_status",
            description="查询订单状态",
            category=ToolCategory.QUERY,
            risk_level=RiskLevel.LOW,
            schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"}
                },
                "required": ["order_id"]
            }
        )

    async def execute(self, arguments: dict) -> ToolResult:
        order_id = arguments.get("order_id")
        # 查询逻辑...
        return ToolResult(
            success=True,
            data={"order_id": order_id, "status": "completed"},
            metadata={"latency_ms": 150}
        )

# 2. 注册工具
from app.tools import ToolRegistry, get_tool_registry

registry = get_tool_registry()
registry.register(QueryOrderTool())

# 3. 获取并执行工具
tool = registry.get("query_order_status")
result = await tool.execute({"order_id": "ORD-123"})

if result.success:
    print(f"订单状态: {result.data['status']}")
else:
    print(f"执行失败: {result.error}")

# 4. 按类别过滤工具
query_tools = registry.filter_by_category(ToolCategory.QUERY)

# 5. 按风险等级过滤
safe_tools = registry.filter_by_risk_level(RiskLevel.MEDIUM, include_lower=True)

# 6. 使用 ToolBusClient 远程调用
from app.tools import ToolBusClient, get_tool_bus_client

client = get_tool_bus_client()
result = await client.execute_tool(
    tool_name="query_order_status",
    arguments={"order_id": "ORD-123"},
    tenant_id="tenant_001",
    user_id="user_123"
)

# 7. 参数校验
from app.tools.validators import validate_tool_arguments

is_valid, errors = validate_tool_arguments(
    tool_definition=tool.metadata.schema,
    arguments={"order_id": "ORD-123"}
)

# 8. FastAPI Depends 使用
from fastapi import Depends
from app.tools import get_tool_registry, ToolRegistry

@app.get("/tools")
async def list_tools(registry: ToolRegistry = Depends(get_tool_registry)):
    return registry.list_all()
```

【安全原则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- [S-AGENT-06] 五层鉴权：RBAC → 租户隔离 → ABAC → 频率限制 → 风险等级
- [S-AGENT-08] 工具调用超时限制（默认 15s）
- [S-AGENT-11] 高风险工具需要审批（requires_approval=True）

【参考】
- Python Protocol PEP 544: https://peps.python.org/pep-0544/
- Registry Pattern: https://martinfowler.com/eaaCatalog/registry.html
- JSON Schema Draft-07: https://json-schema.org/specification-links.html
"""

from app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
    ToolExecutionError,
    ToolMetadata,
    ToolProtocol,
    ToolResult,
)
from app.tools.clients import (
    ModelGatewayClient,
    ToolBusClient,
    get_model_gateway_client,
    get_tool_bus_client,
)
from app.tools.registry import (
    ToolNotFoundError,
    ToolRegistrationError,
    ToolRegistry,
    get_tool_registry,
    reset_tool_registry,
)

__all__ = [
    # Base classes
    "BaseTool",
    "ToolProtocol",
    "ToolResult",
    "ToolMetadata",
    "ToolExecutionError",
    "RiskLevel",
    "ToolCategory",
    # Registry
    "ToolRegistry",
    "ToolNotFoundError",
    "ToolRegistrationError",
    "get_tool_registry",
    "reset_tool_registry",
    # Clients
    "ToolBusClient",
    "get_tool_bus_client",
    "ModelGatewayClient",
    "get_model_gateway_client",
]
