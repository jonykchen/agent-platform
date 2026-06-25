# 通信契约 — 接口规范与版本治理

> **版本**：v2.1 | **状态**：开发中 | **对应审查项**：C-04, C-05, E-05

---

## 1. 统一错误码协议（C-04 补充）

### 1.1 Protobuf 错误码定义

```protobuf
// contracts/proto/common/error_code.proto
syntax = "proto3";
package common;

option java_package = "com.platform.common";
option java_multiple_files = true;

// ============================================================
//  统一错误码定义 (C-04)
//  对应文档: 02-communication-contracts.md §1
// ============================================================

// ErrorCode 枚举 - 全平台统一错误码
enum ErrorCode {
  // ====== 通用错误 (10xxx) ======
  ERR_UNKNOWN = 0;
  ERR_INVALID_REQUEST = 10001;      // 请求参数有误
  ERR_UNAUTHORIZED = 10002;         // 未授权
  ERR_FORBIDDEN = 10003;            // 无权限
  ERR_NOT_FOUND = 10004;            // 资源不存在
  ERR_RATE_LIMITED = 10005;         // 请求过于频繁
  ERR_TIMEOUT = 10006;              // 请求超时
  ERR_SERVICE_UNAVAILABLE = 10007;  // 服务不可用
  ERR_INTERNAL = 10008;             // 内部错误
  ERR_VERSION_MISMATCH = 10009;     // 版本不匹配

  // ====== Agent 编排错误 (20xxx) ======
  ERR_AGENT_MAX_STEPS_EXCEEDED = 20001;     // 超过最大步骤数
  ERR_AGENT_CONTEXT_TOO_LONG = 20002;       // 上下文过长
  ERR_AGENT_TOOL_NOT_FOUND = 20003;         // 工具不存在
  ERR_AGENT_TASK_CANCELLED = 20004;         // 任务被取消
  ERR_AGENT_SESSION_CLOSED = 20005;         // 会话已关闭

  // ====== 模型网关错误 (30xxx) ======
  ERR_MODEL_ALL_PROVIDERS_DOWN = 30001;     // 所有模型提供商不可用
  ERR_MODEL_CONTENT_FILTERED = 30002;       // 内容被安全过滤
  ERR_MODEL_RATE_LIMITED = 30003;           // 模型调用限流
  ERR_MODEL_TIMEOUT = 30004;                // 模型调用超时
  ERR_MODEL_TOKEN_LIMIT_EXCEEDED = 30005;   // Token 限制超出
  ERR_MODEL_RESPONSE_INVALID = 30006;       // 模型响应格式无效
  ERR_MODEL_PROVIDER_ERROR = 30007;         // 模型提供商错误

  // ====== 工具总线错误 (40xxx) ======
  ERR_TOOL_VALIDATION_FAILED = 40001;       // 工具参数校验失败
  ERR_TOOL_EXECUTION_FAILED = 40002;        // 工具执行失败
  ERR_TOOL_RISK_REJECTED = 40003;           // 操作被风控拒绝
  ERR_TOOL_APPROVAL_REQUIRED = 40004;       // 需要人工审批
  ERR_TOOL_TIMEOUT = 40005;                 // 工具调用超时
  ERR_TOOL_NOT_AVAILABLE = 40006;           // 工具不可用

  // ====== 风控审批错误 (50xxx) ======
  ERR_APPROVAL_PENDING = 50001;             // 审批进行中
  ERR_APPROVAL_REJECTED = 50002;            // 审批被拒绝
  ERR_APPROVAL_EXPIRED = 50003;             // 审批已过期
  ERR_APPROVAL_NOT_FOUND = 50004;           // 审批任务不存在
  ERR_RISK_CHECK_FAILED = 50005;            // 风控检查失败

  // ====== 知识库错误 (60xxx) ======
  ERR_KNOWLEDGE_NOT_FOUND = 60001;          // 知识不存在
  ERR_KNOWLEDGE_INDEXING_FAILED = 60002;    // 索引失败
  ERR_KNOWLEDGE_QUERY_FAILED = 60003;       // 查询失败

  // ====== 租户配额错误 (70xxx) ======
  ERR_TENANT_QUOTA_EXCEEDED = 70001;        // 租户配额超出
  ERR_USER_QUOTA_EXCEEDED = 70002;          // 用户配额超出
  ERR_SESSION_QUOTA_EXCEEDED = 70003;       // 会话配额超出
}

// ====== 错误详情消息 ======
message ErrorDetail {
  ErrorCode code = 1;                  // 错误码
  string message = 2;                  // 内部错误消息（面向开发者）
  string user_message = 3;             // 用户友好消息（面向终端用户）
  map<string, string> details = 4;     // 额外详情
  string request_id = 5;               // 请求追踪 ID
  string trace_id = 6;                 // OpenTelemetry Trace ID
  int64 timestamp = 7;                 // 错误发生时间戳
  string service = 8;                  // 来源服务
}

// ====== 通用响应包装 ======
message ApiResponse {
  bool success = 1;                           // 是否成功
  oneof payload {
    google.protobuf.Value data = 2;           // 成功时的数据（任意 JSON）
    ErrorDetail error = 3;                    // 失败时的错误信息
  }
  string request_id = 4;                     // 请求 ID
  int64 timestamp_ms = 5;                    // 响应时间戳
}
```

### 1.2 错误码使用规范

| 规则 | 说明 |
|---|---|
| **码段分配** | 每个 10000 号为一个域，新域需评审 |
| **向后兼容** | 已发布的错误码永不复用或改变含义 |
| **国际化** | `message` 为英文（给开发者），`user_message` 为中文（给终端用户） |
| **日志关联** | 每个错误响应必须携带 `request_id` 和 `trace_id` |
| **重试指导** | 可重试的错误（timeout/rate_limit）应带 `retry_after_seconds` |

---

## 2. 通用 Header 协议（补充完善）

```protobuf
// contracts/proto/common/header.proto
syntax = "proto3";
package platform.common;

// ====== 请求头（所有内部接口必须携带）=====
message RequestHeader {
  string request_id = 1;          // 必须：全局唯一请求ID (UUID v7)
  string tenant_id = 2;           // 必须：租户标识
  string user_id = 3;             // 必须：用户标识
  string trace_id = 4;            // 必须：OpenTelemetry Trace ID
  int64 timestamp = 5;            // 必须：请求时间戳 (ms epoch)
  string source_service = 6;      // 来源服务名
  string locale = 7;              // 可选：语言偏好 (zh-CN/en-US)
  map<string, string> extension = 8; // 扩展字段（预留）
}

// ====== 写操作的幂等头 ======
message WriteRequestHeader {
  RequestHeader base = 1;         // 继承通用头
  string idempotency_key = 2;     // 必须：幂等键（调用方生成 UUID）
  int32 idempotency_ttl_seconds = 3; // 幂等键有效期（默认 86400 = 24h）
}

// ====== 分页参数 ======
message PageRequest {
  int32 page_number = 1;          // 页码（从 1 开始）
  int32 page_size = 2;            // 每页大小（1-100，默认 20）
  string sort_by = 3;             // 排序字段
  bool sort_descending = 4;       // 是否降序
}

// ====== 分页响应 ======
message PageResponse {
  repeated items items = 1;       // 当前页数据（泛型，实际用 any 类型）
  int64 total_count = 2;          // 总记录数
  int32 page_number = 3;          // 当前页码
  int32 total_pages = 4;          // 总页数
  bool has_next = 5;              // 是否有下一页
}
```

---

## 3. 核心服务接口定义（Protobuf）

### 3.1 Gateway ↔ Orchestrator

```protobuf
// contracts/proto/gateway_orchestrator.proto
syntax = "proto3";
package platform.gateway;
import "common/error_code.proto";
import "common/header.proto";

service OrchestratorService {
  // 处理聊天补全请求（同步 + SSE streaming）
  rpc ChatCompletion(ChatCompletionRequest) returns (stream ChatCompletionChunk);
  
  // 启动一次 Agent 运行
  rpc StartAgentRun(AgentRunRequest) returns (AgentRunResponse);
  
  // 查询 Agent 运行状态
  rpc GetAgentRunStatus(GetRunStatusRequest) returns (GetRunStatusResponse);
  
  // 取消正在运行的 Agent
  rpc CancelAgentRun(CancelRunRequest) returns (CancelRunResponse);
}

message ChatCompletionRequest {
  platform.common.RequestHeader header = 1;
  string message = 2;                    // 用户输入
  repeated MessageHistory history = 3;   // 历史对话（最近 N 轮）
  string session_id = 4;                 // 会话 ID（新建时留空）
  AgentOptions options = 5;              // 可选参数
}

message ChatCompletionChunk {
  string chunk_id = 1;                   // Chunk 标识
  string delta_content = 2;              // 增量文本内容
  bool is_final = 3;                     // 是否最后一个 chunk
  FinishReason finish_reason = 4;        // 结束原因
  Usage usage = 5;                       // Token 用量
  AgentStepInfo step_info = 6;          // 当前步骤信息（如果有）
}

enum FinishReason {
  FINISH_STOP = 0;
  FINISH_TOOL_CALL = 1;
  FINISH_LENGTH = 2;
  FINISH_ERROR = 3;
}

message Usage {
  int32 prompt_tokens = 1;
  int32 completion_tokens = 2;
  int32 total_tokens = 3;
}

message AgentOptions {
  float temperature = 1;
  int32 max_tokens = 2;
  bool stream = 3;                       // 是否流式输出（默认 true）
  repeated string enabled_tools = 4;    // 白名单工具（空=全部可用）
  string model_override = 5;             // 强制指定模型
}

// ... (AgentRun 相关消息略，按类似风格定义)
```

### 3.2 Orchestrator ↔ Tool Bus

```protobuf
// contracts/proto/tool_bus.proto
syntax = "proto3";
package platform.toolbus;
import "common/error_code.proto";
import "common/header.proto";

service ToolBusService {
  // 执行工具调用
  rpc ExecuteTool(ToolExecuteRequest) returns (ToolExecuteResponse);
  
  // 批量执行多个工具（并行）
  rpc BatchExecuteTools(BatchToolExecuteRequest) returns (stream ToolExecuteResult);
  
  // 列出可用工具
  rpc ListTools(ListToolsRequest) returns (ListToolsResponse);
  
  // 校验工具参数（不执行）
  rpc ValidateToolParams(ValidateParamsRequest) returns (ValidateParamsResponse);
}

message ToolExecuteRequest {
  platform.common.WriteRequestHeader header = 1;
  string tool_name = 2;                   // 工具名称
  google.protobuf.Struct parameters = 3;  // 工具参数 (JSON)
  RiskContext risk_context = 4;           // 风险评估上下文
  ExecutionOptions options = 5;           // 执行选项
}

message ToolExecuteResponse {
  bool success = 1;
  oneof result {
    google.protobuf.Struct output_data = 2;  // 正确返回的数据 (JSON)
    platform.common.ErrorDetail error = 3;   // 执行错误
  }
  ToolExecutionMetadata metadata = 4;      // 执行元数据
}

message RiskContext {
  string previous_tools = 1;              // 本次运行中之前调用的工具（逗号分隔）
  int32 tool_call_count_in_session = 2;    // 当前会话中的工具调用次数
  string user_intent_summary = 3;         // 用户意图摘要
}

message ExecutionOptions {
  int32 timeout_ms = 1;                   // 超时时间（毫秒）
  bool skip_risk_check = 2;               // 是否跳过风控（仅内部使用）
  bool skip_approval = 3;                 // 是否跳过审批（仅内部使用）
}

message ToolExecutionMetadata {
  string execution_id = 1;                // 执行 ID
  int64 duration_ms = 2;                 // 耗时
  string provider_latency_ms = 3;         // 下游系统延迟
  bool was_cached = 4;                   // 是否命中缓存
  bool required_approval = 5;             // 是否触发了审批
  string approval_id = 6;                // 关联的审批 ID
}
```

---

## 4. 工具动态注册 API（C-05 补充）

### 4.1 注册端点定义

**Base URL**: `/internal/tools` （仅内网可访问，需要 Service Token 认证）

| 方法 | 路径 | 功能 | 认证 |
|---|---|---|---|
| `POST` | `/internal/tools/register` | 注册新工具 | Admin |
| `GET` | `/internal/tools` | 列出所有可用工具 | Service Token |
| `GET` | `/internal/tools/{name}` | 获取工具详情 | Service Token |
| `PUT` | `/internal/tools/{name}` | 更新工具配置 | Admin |
| `POST` | `/internal/tools/{name}/enable` | 启用工具 | Admin |
| `POST` | `/internal/tools/{name}/disable` | 禁用工具 | Admin |
| `DELETE` | `/internal/tools/{name}` | 下线工具（仅 sunset 状态） | Admin |

### 4.2 注册请求/响应 Schema

```jsonc
// POST /internal/tools/register — 请求体
{
  "name": "query_inventory",
  "description": "查询商品库存信息",
  "version": "1.0",
  "category": "query",              // query / write / external
  "risk_level": "low",             // low / medium / high / critical
  
  // JSON Schema 格式的参数定义
  "parameters": {
    "type": "object",
    "properties": {
      "sku": {
        "type": "string",
        "description": "商品SKU编码"
      },
      "warehouse_id": {
        "type": "string",
        "description": "仓库ID（可选，默认查全部）"
      }
    },
    "required": ["sku"]
  },

  // 执行配置
  "endpoint": "http://inventory-service.internal:8080/api/query",
  "method": "GET",
  "auth_type": "service_token",     // service_token / oauth2 / api_key / none
  "timeout_ms": 5000,
  
  // 权限配置
  "allowed_roles": ["admin", "operator"],
  "daily_quota_per_user": 1000,

  // 元数据
  "tags": ["inventory", "read-only"],
  "owner_team": "supply-chain",
  "enabled": true
}
```

```jsonc
// 响应体（成功）
{
  "success": true,
  "data": {
    "tool_name": "query_inventory",
    "version": "1.0",
    "status": "active",
    "registered_at": "2026-05-08T10:30:00Z",
    "tool_id": "tool_uuid_xxx"
  },
  "request_id": "req_abc123"
}
```

### 4.3 工具生命周期状态机

```
                    ┌─────────────┐
                    │   draft     │  ← 注册后的初始状态
                    └──────┬──────┘
                           │ POST /enable
                           ▼
              ┌──────────────────────┐
              │      active          │  ← 可正常调用
              └──┬───────────────┬───┘
                 │               │
     POST /disable        POST /deprecate
                 ▼               ▼
        ┌────────────┐  ┌──────────────┐
        │  disabled  │  │  deprecated  │  ← 响应含 Deprecation header
        └─────┬──────┘  └──────┬───────┘
              │               │ sunset 日期到达 或 DELETE
              │               ▼
              │        ┌──────────┐
              │        │  sunset  │  ← 返回 410 Gone
              │        └──────────┘
              │ enable         │
              └───────────────┘
```

---

## 5. API 契约测试机制（E-05 补充）

### 5.1 CI Pipeline 中的契约测试阶段

```yaml
# ci/templates/contract-test.yml
contract-test:
  stage: contract-test
  image: bufbuild/buf:latest
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  script:
    # 1. Protobuf Breaking Change 检测（防止破坏性变更）
    - buf breaking --against 'branch=main' contracts/proto
    
    # 2. Protobuf Lint 检查
    - buf lint contracts/proto
    
    # 3. OpenAPI 兼容性检查
    - spectral lint contracts/openapi/*.yaml --ruleset .spectral.yaml
    
    # 4. gRPC 接口兼容性测试（mock server）
    - |
      # 启动 mock server
      grpcurl -plaintext \
        -d '{"header":{"request_id":"test","tenant_id":"test_tenant","user_id":"test_user","trace_id":"","timestamp":0},"message":"hello"}' \
        --import-path contracts/proto \
        -proto gateway_orchestrator.proto \
        localhost:50100 \
        platform.gateway.OrchestratorService/ChatCompletion
  
  artifacts:
    reports:
      junit: buf-report.xml
  allow_failure: false
```

### 5.2 Spectral 规则集（OpenAPI 规则）

```yaml
# .spectral.yaml
extends: ["spectral:oas"]
rules:
  # 所有接口必须有 operationId
  operation-operationId: error
  
  # 所有 Schema 必须有 description
  info-description: warn
  info-contact: warn
  info-license: off
  
  # 必须携带通用 Header
  no-$ref-siblings: error
  
  # 版本路径必须包含 major version
  path-declarations-must-exist: error
  
  # 响应必须包含 error schema
  oas3-valid-schema-example: warn
```

---

## 6. 事件契约（Kafka Event Schema）

### 6.1 事件命名规范

```
{domain}.{resource}.{action}

示例：
tool.invocation.completed     — 工具调用完成
agent.run.started             — Agent 运行开始
agent.step.completed          — 步骤完成
approval.task.created         — 审批任务创建
audit.event.published         — 审计事件发布
model.call.completed          — 模型调用完成
session.created               — 会话创建
token.quota.exceeded          — Token 配额超限
```

### 6.2 核心事件 Schema

```jsonc
// tool.invocation.completed
{
  "$id": "event/tool_invocation_completed.json",
  "type": "object",
  "required": ["event_id", "event_type", "timestamp", "source", "data"],
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"const": "tool.invocation.completed"},
    "timestamp": {"type": "string", "format": "date-time"},
    "source": {"const": "tool-bus"},
    "version": {"type": "integer", "minimum": 1},
    "data": {
      "type": "object",
      "properties": {
        "request_id": {"type": "string"},
        "run_id": {"type": "string", "format": "uuid"},
        "step_id": {"type": "string", "format": "uuid"},
        "tool_name": {"type": "string"},
        "input_data": {"type": "object"},
        "output_data": {"type": "object"},
        "status": {"enum": ["success", "failed", "rejected", "timeout"]},
        "error_code": {"type": "string"},
        "duration_ms": {"type": "integer"},
        "risk_level": {"type": "string"}
      }
    },
    "metadata": {
      "tenant_id": {"type": "string"},
      "user_id": {"type": "string"},
      "trace_id": {"type": "string"},
      "partition_key": {"type": "string"}  // Kafka 分区键
    }
  }
}
```

---

## 7. API 版本治理（§10 完整补充）

### 7.1 版本号规范

采用语义化版本号：`v{major}.{minor}.{patch}`

| 层级 | 变更类型 | 示例 |
|---|---|---|
| **Major** | 破坏性变更（不兼容的接口修改） | v1 → v2 |
| **Minor** | 功能新增（向后兼容） | v1.0 → v1.1 |
| **Patch** | Bug 修复（向后兼容） | v1.0.0 → v1.0.1 |

### 7.2 URL 路径版本策略

```
# 推荐方式：路径版本
POST /api/v1/chat/completions
POST /api/v2/chat/completions

# 不推荐：Header 版本（增加调试复杂度）
# X-API-Version: 2024-01-01
```

**规则**：
- Major 版本变更必须创建新路径（`/v1/` → `/v2/`）
- Minor/Patch 版本变更保持路径不变
- 至多同时支持 2 个 Major 版本（如 v1 和 v2）

### 7.3 版本废弃流程

```
┌─────────────────────────────────────────────────────────────────────┐
│                        API 版本生命周期                               │
│                                                                      │
│  发布 → 稳定期 → 废弃公告 → 灰度警告 → 强制下线                        │
│   │       │         │           │            │                      │
│   │       │         │           │            └─ 返回 410 Gone       │
│   │       │         │           └─ Response Header:                 │
│   │       │         │              Sunset: Sat, 01 Jan 2027        │
│   │       │         └─ 公告期 ≥ 90 天                                │
│   │       └─ 至少 12 个月稳定支持                                    │
│   └─ 文档、SDK、示例同步发布                                         │
└─────────────────────────────────────────────────────────────────────┘
```

**废弃通知机制**：
1. **公告阶段**：在 API 文档、开发者门户发布公告
2. **灰度警告**：在响应头添加 `Deprecation: true` 和 `Sunset` 日期
3. **邮件通知**：向受影响租户发送迁移提醒
4. **强制下线**：返回 `410 Gone`，响应体包含迁移指南链接

### 7.4 多版本并存策略

| 场景 | 策略 |
|---|---|
| **内部服务间调用** | 统一使用最新稳定版本 |
| **外部 OpenAPI** | 支持 v1/v2 并存，逐步引导迁移 |
| **SDK 兼容** | SDK 默认使用最新版本，支持显式指定版本 |

**版本路由规则**：
```yaml
# Gateway 路由配置示例
routes:
  - path: /api/v1/*
    service: orchestrator-v1
    sunset: "2027-06-01"

  - path: /api/v2/*
    service: orchestrator-v2
    default: true
```

### 7.5 版本变更 Checklist

- [ ] 更新 OpenAPI 规范文件（`contracts/openapi/`）
- [ ] 更新 SDK 和客户端库
- [ ] 更新 API 文档和示例代码
- [ ] 如有破坏性变更，提前 90 天发布公告
- [ ] 灰度期间监控旧版本调用量，确认迁移进度
- [ ] 下线前再次通知未迁移租户
