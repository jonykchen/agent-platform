"""工具客户端模块 - 与外部服务通信

【模块架构】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ┌─────────────────────────────────┐
                    │         Orchestrator            │
                    │        (Python Agent)          │
                    └─────────────────┬───────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLIENTS MODULE                                    │
│                                                                             │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐        │
│  │      ToolBusClient          │    │    ModelGatewayClient        │        │
│  │   (gRPC 客户端)             │    │    (HTTP 客户端)             │        │
│  ├─────────────────────────────┤    ├─────────────────────────────┤        │
│  │ • 工具执行请求              │    │ • 模型调用请求              │        │
│  │ • 熔断器保护                │    │ • 多提供商路由              │        │
│  │ • 重试策略                  │    │ • Token 计数                │        │
│  │ • 超时控制                  │    │ • 响应缓存                  │        │
│  │ • 审批流程对接              │    │ • 流式响应支持              │        │
│  └─────────────────────────────┘    └─────────────────────────────┘        │
│              │                                    │                        │
│              │ gRPC                               │ HTTP                    │
│              ▼                                    ▼                        │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐        │
│  │   ToolBus Service (Java)    │    │   Model Gateway (Python)    │        │
│  │   localhost:50051          │    │   localhost:8002            │        │
│  │                             │    │                             │        │
│  │ • 工具执行引擎              │    │ • Qwen/GLM/Kimi/DeepSeek   │        │
│  │ • 风控审批                  │    │ • 负载均衡                  │        │
│  │ • 审计日志                  │    │ • 成本追踪                  │        │
│  │ • 权限校验                  │    │ • 内容过滤                  │        │
│  └─────────────────────────────┘    └─────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘

【子模块职责】
┌────────────────────┬──────────────────────────────────────────────────────────────┐
│ 子模块              │ 职责描述                                                      │
├────────────────────┼──────────────────────────────────────────────────────────────┤
│ tool_bus_client    │ ToolBus gRPC 客户端：工具执行、审批流程对接、熔断保护          │
│ model_gateway_     │ ModelGateway HTTP 客户端：模型调用、Token 计数、流式响应       │
│ client             │                                                              │
└────────────────────┴──────────────────────────────────────────────────────────────┘

【核心组件】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. ToolBusClient
   ━━━━━━━━━━━━━━━━━━━━━━
   - 协议: gRPC (高性能二进制传输)
   - 功能:
     • execute_tool(): 执行工具并返回结果
     • request_approval(): 提交审批请求
     • check_approval_status(): 查询审批状态
   - 容错:
     • 熔断器保护 (CircuitBreaker)
     • 指数退避重试 (RetryPolicy)
     • 超时控制 (DEFAULT_TIMEOUT=15s)
   - 配置:
     • tool_bus_grpc_addr: gRPC 地址
     • max_message_length: 16MB

2. ModelGatewayClient
   ━━━━━━━━━━━━━━━━━━━━━━
   - 协议: HTTP/2 (httpx async client)
   - 功能:
     • invoke(): 调用模型生成响应
     • invoke_stream(): 流式调用
     • count_tokens(): Token 计数
   - 特性:
     • 多提供商路由 (Qwen/GLM/Kimi/DeepSeek)
     • 响应缓存 (相同 prompt 缓存结果)
     • 请求去重 (防止重复调用)
   - 配置:
     • model_gateway_url: HTTP 地址
     • max_connections: 连接池大小

【技术选型】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ToolBus 使用 gRPC vs HTTP 的原因:
┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 协议               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ gRPC (选择)        │ • 高性能二进制传输          │ • 需要 Proto 定义           │
│                    │ • 强类型约束                │ • 调试较复杂                │
│                    │ • 双向流支持                │                              │
│                    │ • 内置超时/重试             │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ HTTP REST          │ • 简单易用                  │ • JSON 文本传输效率低       │
│                    │ • 无需额外定义              │ • 无强类型约束              │
│                    │ • 易于调试                  │                              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

ModelGateway 使用 HTTP 的原因:
- 模型 API 本身是 HTTP 协议
- 便于调试（可查看请求/响应内容）
- 支持流式响应 (SSE)

【使用示例】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# 1. ToolBusClient - 工具执行
from app.tools.clients import ToolBusClient, get_tool_bus_client

client = get_tool_bus_client()

# 执行工具
result = await client.execute_tool(
    tool_name="query_order_status",
    arguments={"order_id": "ORD-123"},
    tenant_id="tenant_001",
    user_id="user_123",
    request_id="req_abc"
)

if result.success:
    print(f"订单状态: {result.data}")
else:
    print(f"错误: {result.error}")

# 2. ToolBusClient - 审批流程
# 提交审批
approval_id = await client.request_approval(
    tool_name="execute_payment",
    arguments={"amount": 10000, "account": "xxx"},
    tenant_id="tenant_001",
    user_id="user_123",
    risk_level="high"
)

# 查询审批状态
status = await client.check_approval_status(approval_id)
if status.status == "approved":
    # 继续执行
    result = await client.execute_tool(...)

# 3. ModelGatewayClient - 模型调用
from app.tools.clients import ModelGatewayClient, get_model_gateway_client

model_client = get_model_gateway_client()

# 同步调用
response = await model_client.invoke(
    model="qwen-max",
    messages=[
        {"role": "user", "content": "你好"}
    ],
    temperature=0.7,
    max_tokens=2000
)

print(response.content)

# 4. ModelGatewayClient - 流式调用
async for chunk in model_client.invoke_stream(
    model="qwen-max",
    messages=[{"role": "user", "content": "写一段代码"}]
):
    print(chunk.delta, end="", flush=True)

# 5. ModelGatewayClient - Token 计数
token_count = await model_client.count_tokens(
    messages=[{"role": "user", "content": "这是一段文本"}]
)
print(f"Token 数: {token_count}")

# 6. 直接使用单例函数（推荐）
from app.tools.clients import get_tool_bus_client, get_model_gateway_client

tool_client = get_tool_bus_client()
model_client = get_model_gateway_client()
```

【配置项】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# config.py 中的相关配置
tool_bus_grpc_addr: str = "localhost:50051"  # ToolBus gRPC 地址
model_gateway_url: str = "http://localhost:8002"  # Model Gateway HTTP 地址

tool_call_timeout_s: int = 15  # 工具调用超时
model_call_timeout_s: int = 30  # 模型调用超时

http_max_connections: int = 100  # HTTP 最大连接数
http_max_keepalive: int = 20     # HTTP keepalive 连接数
```

【安全原则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- [S-AGENT-06] 所有调用携带 tenant_id/user_id 用于鉴权
- [S-AGENT-08] 超时控制防止长时间阻塞
- [G-SEC-01] API Key 通过环境变量注入，不硬编码

【参考】
- gRPC Python 文档: https://grpc.io/docs/languages/python/
- httpx 异步客户端: https://www.python-httpx.org/async/
"""

from app.tools.clients.model_gateway_client import ModelGatewayClient, get_model_gateway_client
from app.tools.clients.tool_bus_client import ToolBusClient, get_tool_bus_client

__all__ = [
    "ToolBusClient",
    "get_tool_bus_client",
    "ModelGatewayClient",
    "get_model_gateway_client",
]
