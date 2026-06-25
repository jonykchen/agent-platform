# API 参考文档

> **版本**: v1.0
> **状态**: 已批准
> **所有者**: Platform Team
> **更新**: 2026-06-24

本文档汇总 Agent Platform 的所有 API 端点和使用示例。

---

## 目录

1. [认证](#认证)
2. [对话接口](#对话接口)
3. [Agent 任务](#agent-任务)
4. [会话管理](#会话管理)
5. [审批流程](#审批流程)
6. [健康检查](#健康检查)
7. [错误码](#错误码)

---

## 基础信息

### Base URL

| 环境 | URL |
|------|-----|
| 本地开发 | http://localhost:8080 |
| 生产环境 | https://api.agent-platform.example.com |

### 请求头

所有请求必须包含以下请求头：

| 请求头 | 必需 | 说明 |
|--------|------|------|
| `Authorization` | ✅ | Bearer Token 认证 |
| `X-Tenant-ID` | ✅ | 租户 ID |
| `X-User-ID` | ✅ | 用户 ID |
| `X-Request-ID` | 可选 | 请求唯一标识（自动生成） |
| `Content-Type` | ✅ | `application/json` |

---

## 认证

### 登录

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "password"
}
```

**响应示例**：

```json
{
  "tokens": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
  },
  "user": {
    "id": "user-123",
    "email": "admin@example.com",
    "name": "Admin User",
    "roles": ["admin"]
  },
  "tenant": {
    "id": "tenant-123",
    "name": "Test Tenant",
    "tier": "enterprise",
    "features": ["chat", "knowledge", "tools"]
  }
}
```

### 刷新 Token

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**响应示例**：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 3600
}
```

### 登出

```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

**响应示例**：

```json
{
  "message": "登出成功"
}
```

---

## 对话接口

### 发送对话（流式）

```http
POST /api/v1/chat/completions
Authorization: Bearer <access_token>
X-Tenant-ID: tenant-123
X-User-ID: user-123
Content-Type: application/json

{
  "message": "你好，请帮我查询今天的订单状态",
  "session_id": "session-abc123",
  "model": "qwen-max",
  "temperature": 0.7,
  "max_tokens": 2000,
  "stream": true,
  "enable_rag": true,
  "enable_tools": true
}
```

**响应示例（SSE 流式）**：

```
event: message
data: {"delta_content": "你好", "is_final": false}

event: message
data: {"delta_content": "！我来帮你查询订单状态。", "is_final": false}

event: message
data: {"delta_content": "", "is_final": true, "tool_calls": [{"call_id": "call-123", "tool_name": "query_order_status", "arguments": {"date": "2026-06-24"}}]}

event: message
data: {"delta_content": "根据查询结果，今天共有 5 个订单...", "is_final": true}
```

### 发送对话（非流式）

```http
POST /api/v1/chat/completions
Authorization: Bearer <access_token>
X-Tenant-ID: tenant-123
X-User-ID: user-123
Content-Type: application/json

{
  "message": "你好",
  "stream": false
}
```

**响应示例**：

```json
{
  "request_id": "req-abc123",
  "session_id": "session-xyz789",
  "response": "你好！有什么我可以帮助你的吗？",
  "model_used": "qwen-max",
  "prompt_tokens": 10,
  "completion_tokens": 15,
  "total_tokens": 25,
  "cost_usd": 0.001,
  "latency_ms": 1234,
  "finish_reason": "stop",
  "tool_calls": [],
  "approval_id": null
}
```

### 请求参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `message` | string | ✅ | - | 用户输入消息（1-8000 字符） |
| `session_id` | string | 可选 | 自动生成 | 会话 ID |
| `model` | string | 可选 | 默认模型 | 指定模型（如 `qwen-max`） |
| `temperature` | number | 可选 | 0.7 | 温度参数（0-2） |
| `max_tokens` | integer | 可选 | 2000 | 最大输出 token 数（1-8000） |
| `stream` | boolean | 可选 | false | 是否流式输出 |
| `enable_rag` | boolean | 可选 | true | 是否启用 RAG |
| `enable_tools` | boolean | 可选 | true | 是否启用工具调用 |

### 响应字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `request_id` | string | 请求唯一标识 |
| `session_id` | string | 会话 ID |
| `response` | string | AI 响应内容 |
| `model_used` | string | 使用的模型 |
| `prompt_tokens` | integer | 输入 token 数 |
| `completion_tokens` | integer | 输出 token 数 |
| `total_tokens` | integer | 总 token 数 |
| `cost_usd` | number | 费用（美元） |
| `latency_ms` | integer | 延迟（毫秒） |
| `finish_reason` | string | 结束原因（stop/tool_call/error/length） |
| `tool_calls` | array | 工具调用列表 |
| `approval_id` | string | 审批单 ID（如需审批） |

---

## Agent 任务

### 启动任务

```http
POST /api/v1/agents/{agent_id}/runs
Authorization: Bearer <access_token>
X-Tenant-ID: tenant-123
X-User-ID: user-123
Content-Type: application/json

{
  "task": "帮我生成一份销售报告",
  "session_id": "session-abc123",
  "parameters": {
    "date_range": "2026-06-01 to 2026-06-24",
    "format": "pdf"
  },
  "execution_mode": "react",
  "max_steps": 10
}
```

**响应示例**：

```json
{
  "run_id": "run-xyz789",
  "session_id": "session-abc123",
  "status": "running",
  "result": null,
  "steps": [],
  "total_tokens": 0,
  "cost_usd": 0,
  "duration_ms": 0
}
```

### 查询任务状态

```http
GET /api/v1/agents/{agent_id}/runs/{run_id}
Authorization: Bearer <access_token>
X-Tenant-ID: tenant-123
X-User-ID: user-123
```

**响应示例**：

```json
{
  "run_id": "run-xyz789",
  "status": "completed",
  "current_step": null,
  "completed_steps": 5,
  "approval_id": null
}
```

### 任务状态

| 状态 | 说明 |
|------|------|
| `pending` | 等待执行 |
| `running` | 执行中 |
| `completed` | 已完成 |
| `failed` | 执行失败 |
| `cancelled` | 已取消 |
| `waiting_approval` | 等待审批 |

---

## 会话管理

### 获取会话详情

```http
GET /api/v1/sessions/{session_id}
Authorization: Bearer <access_token>
X-Tenant-ID: tenant-123
X-User-ID: user-123
```

**响应示例**：

```json
{
  "session_id": "session-abc123",
  "user_id": "user-123",
  "title": "查询订单状态",
  "status": "active",
  "run_count": 3,
  "created_at": "2026-06-24T10:30:00Z",
  "updated_at": "2026-06-24T11:45:00Z"
}
```

### 会话状态

| 状态 | 说明 |
|------|------|
| `active` | 活跃 |
| `archived` | 已归档 |
| `deleted` | 已删除 |

---

## 审批流程

### 处理审批

```http
POST /api/v1/approvals/{approval_id}/review
Authorization: Bearer <access_token>
X-Tenant-ID: tenant-123
X-User-ID: user-123
Content-Type: application/json

{
  "decision": "approved",
  "comment": "同意执行"
}
```

**响应示例**：

```json
{
  "id": "approval-123",
  "run_id": "run-xyz789",
  "status": "approved",
  "requester_id": "user-123",
  "assignee_id": "user-456",
  "reason": "高风险操作需要审批",
  "created_at": "2026-06-24T10:30:00Z",
  "expires_at": "2026-06-24T12:30:00Z"
}
```

### 审批决策

| 决策 | 说明 |
|------|------|
| `approved` | 批准 |
| `rejected` | 拒绝 |

---

## 健康检查

### 服务健康

```http
GET /health
```

**响应示例**：

```json
{
  "status": "UP",
  "service": "gateway",
  "version": "1.0.0",
  "checks": {
    "database": "UP",
    "redis": "UP",
    "orchestrator": "UP"
  }
}
```

### 健康状态

| 状态 | 说明 |
|------|------|
| `UP` | 服务正常 |
| `DOWN` | 服务异常 |

---

## 错误码

### 错误响应格式

```json
{
  "error": "ERR_CODE",
  "message": "技术信息",
  "user_message": "用户友好信息",
  "request_id": "req-abc123",
  "details": {}
}
```

### 错误码列表

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| `INVALID_REQUEST` | 400 | 请求参数错误 |
| `UNAUTHORIZED` | 401 | 未授权 |
| `FORBIDDEN` | 403 | 权限不足 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `RATE_LIMITED` | 429 | 请求过于频繁 |
| `INTERNAL_ERROR` | 500 | 服务器内部错误 |
| `SERVICE_UNAVAILABLE` | 503 | 服务不可用 |

### 业务错误码

| 错误码 | 说明 |
|--------|------|
| `AGENT_MAX_STEPS` | Agent 步骤数超限 |
| `CONTEXT_TOO_LONG` | 上下文长度超限 |
| `TOOL_NOT_FOUND` | 工具不存在 |
| `TOOL_EXECUTION_FAILED` | 工具执行失败 |
| `APPROVAL_REQUIRED` | 需要审批 |
| `APPROVAL_EXPIRED` | 审批已过期 |
| `MODEL_CALL_FAILED` | 模型调用失败 |
| `CONTENT_FILTERED` | 内容被过滤 |

---

## 示例代码

### Python

```python
import requests

BASE_URL = "http://localhost:8080"
HEADERS = {
    "Authorization": "Bearer <access_token>",
    "X-Tenant-ID": "tenant-123",
    "X-User-ID": "user-123",
    "Content-Type": "application/json",
}

# 发送对话
response = requests.post(
    f"{BASE_URL}/api/v1/chat/completions",
    headers=HEADERS,
    json={
        "message": "你好",
        "stream": False,
    },
)

print(response.json())
```

### JavaScript

```javascript
const BASE_URL = "http://localhost:8080";
const HEADERS = {
  Authorization: "Bearer <access_token>",
  "X-Tenant-ID": "tenant-123",
  "X-User-ID": "user-123",
  "Content-Type": "application/json",
};

// 发送对话
const response = await fetch(`${BASE_URL}/api/v1/chat/completions`, {
  method: "POST",
  headers: HEADERS,
  body: JSON.stringify({
    message: "你好",
    stream: false,
  }),
});

const data = await response.json();
console.log(data);
```

### cURL

```bash
curl -X POST http://localhost:8080/api/v1/chat/completions \
  -H "Authorization: Bearer <access_token>" \
  -H "X-Tenant-ID: tenant-123" \
  -H "X-User-ID: user-123" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "stream": false
  }'
```

---

## 相关文档

- [OpenAPI 规范](../contracts/openapi/gateway-api.yaml)
- [通信契约](02-communication-contracts.md)
- [安全规范](03-security-specification.md)
- [部署指南](deployment-guide.md)
