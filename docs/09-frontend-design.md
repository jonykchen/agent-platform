# 前端设计 — Web 应用与管理后台

> **版本**：v1.0 | **状态**：📋 规划中 | **对应审查项**：F-01, F-02, F-03

---

## 1. 概述

### 1.1 背景

当前 Agent Platform 为纯后端 API 平台，包含 6 个微服务：
- gateway-java（API 入口）
- orchestrator-python（Agent 编排）
- model-gateway-python（模型网关）
- tool-bus-java（工具总线）
- governance-java（风控+审批）
- knowledge-python（知识库）

本方案设计生产级前端应用，提供：
1. **用户对话界面** — 与 Agent 交互的核心入口
2. **管理后台** — 工具管理、审批处理、审计查看、租户配置
3. **监控面板** — 业务层面的使用统计与成本分析

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **API 契约优先** | 所有类型定义与后端 Protobuf/OpenAPI 保持一致 |
| **安全内置** | JWT 认证、RBAC 权限、多租户隔离在 UI 层强制执行 |
| **渐进增强** | 核心功能无 JS 也可用（SSR），JS 增强交互体验 |
| **可观测** | 前端日志、性能指标、错误上报与后端观测体系打通 |
| **国际化** | 支持中英文切换，错误消息与后端 `user_message` 对齐 |

### 1.3 与现有文档关联

| 本文档章节 | 关联文档 | 关联内容 |
|------------|----------|----------|
| §2 API 类型定义 | [02-communication-contracts.md](./02-communication-contracts.md) | API 端点、错误码、请求响应格式 |
| §3 认证与权限 | [03-security-specification.md](./03-security-specification.md) | JWT、RBAC、ABAC、多租户 |
| §4 数据模型 | [04-data-design-complete.md](./04-data-design-complete.md) | 表结构、字段定义 |
| §5 SSE 流式 | [05-performance-optimization.md](./05-performance-optimization.md) | Fast Path、SSE 格式 |
| §6 多租户 | [07-scalability-patterns.md](./07-scalability-patterns.md) | RLS、配额管理 |

---

## 2. 技术选型

### 2.1 核心框架

| 类别 | 选型 | 版本 | 选型理由 |
|------|------|------|----------|
| **框架** | React | 18.x | 生态成熟、TypeScript 支持好、团队熟悉 |
| **语言** | TypeScript | 5.x | 类型安全、与后端 Protobuf 类型生成兼容 |
| **构建** | Vite | 5.x | 开发体验好、HMR 快、构建产物小 |
| **路由** | TanStack Router | 1.x | 类型安全路由、支持 layouts、数据预加载 |
| **状态** | Zustand | 4.x | 轻量、简单、无 Provider 地狱 |
| **服务端状态** | TanStack Query | 5.x | 缓存、重试、乐观更新、与 SSE 结合好 |
| **样式** | Tailwind CSS | 3.x | 原子化、与 Ant Design 共存、暗色模式 |
| **组件库** | Ant Design | 5.x | 企业级、中文友好、表单/表格强 |
| **图标** | Lucide React | — | 轻量、树摇优化、风格统一 |
| **表单** | React Hook Form | 7.x | 性能好、验证灵活、与 Ant Design 集成 |
| **图表** | ECharts | 5.x | 功能强、中文文档、与 Ant Design 风格一致 |

### 2.2 实时通信

| 场景 | 技术 | 说明 |
|------|------|------|
| 对话流式输出 | Fetch + ReadableStream | 支持 POST + Header 认证，优于原生 EventSource |
| 审批通知推送 | WebSocket | 双向通信、实时通知、在线状态 |
| 连接状态管理 | 自定义 Hook | 统一处理断线重连、心跳检测、Last-Event-ID 恢复 |

### 2.3 类型生成自动化

从后端 OpenAPI 规范自动生成 TypeScript 类型，保持前后端类型一致。

```bash
# 安装工具
pnpm add -D openapi-typescript

# 生成类型（集成到 package.json scripts）
pnpm openapi-typescript http://localhost:8080/api/v1/openapi.yaml \
  -o src/types/api.generated.ts \
  --alphabetize \
  --readonly
```

```json
// package.json
{
  "scripts": {
    "gen:types": "openapi-typescript $VITE_API_URL/openapi.yaml -o src/types/api.generated.ts",
    "gen:watch": "openapi-typescript $VITE_API_URL/openapi.yaml -o src/types/api.generated.ts --watch"
  }
}
```

```typescript
// src/types/api.ts - 统一导出
export * from './api.generated';
export * from './chat';
export * from './approval';
// ...
```

### 2.4 工具链

| 工具 | 用途 |
|------|------|
| **pnpm** | 包管理（Monorepo 支持） |
| **Turborepo** | Monorepo 构建（可选） |
| **ESLint** | 代码检查 |
| **Prettier** | 代码格式化 |
| **Vitest** | 单元测试 |
| **Playwright** | E2E 测试 |
| **Storybook** | 组件文档（可选） |

### 2.5 目录结构

```
services/
└── web-frontend/                    # 前端应用（Monorepo 与后端同级）
    ├── package.json
    ├── pnpm-lock.yaml
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── postcss.config.js
    │
    ├── src/
    │   ├── main.tsx                 # 应用入口
    │   ├── App.tsx                  # 根组件
    │   ├── routes/                  # 路由定义（TanStack Router 文件路由）
    │   │   ├── __root.tsx           # 根布局
    │   │   ├── index.tsx            # 首页
    │   │   ├── chat/
    │   │   │   ├── index.tsx        # 会话列表
    │   │   │   └── $sessionId.tsx   # 对话详情
    │   │   ├── approval/
    │   │   │   ├── index.tsx        # 审批列表
    │   │   │   └── $id.tsx          # 审批详情
    │   │   ├── tools/
    │   │   │   ├── index.tsx        # 工具列表
    │   │   │   └── register.tsx     # 工具注册
    │   │   ├── audit/
    │   │   │   └── index.tsx        # 审计日志
    │   │   ├── tenant/
    │   │   │   └── index.tsx        # 租户配置
    │   │   ├── knowledge/
    │   │   │   ├── index.tsx        # 知识库列表
    │   │   │   └── $docId.tsx       # 文档详情
    │   │   ├── users/
    │   │   │   ├── index.tsx        # 用户列表
    │   │   │   └── roles.tsx        # 角色管理
    │   │   ├── notifications/
    │   │   │   └── index.tsx        # 通知中心
    │   │   ├── dashboard/
    │   │   │   └── index.tsx        # 监控面板
    │   │   └── login.tsx            # 登录页
    │   │
    │   ├── components/              # 共享组件
    │   │   ├── ui/                  # 基础 UI 组件（Button/Input/Modal...）
    │   │   │   ├── FileUpload.tsx   # 文件上传
    │   │   │   └── KeyboardShortcuts.tsx # 快捷键
    │   │   ├── chat/                # 对话相关组件
    │   │   │   ├── MessageList.tsx
    │   │   │   ├── MessageItem.tsx
    │   │   │   ├── InputBox.tsx
    │   │   │   ├── StepVisualizer.tsx
    │   │   │   ├── ToolCallCard.tsx
    │   │   │   └── SessionList.tsx  # 会话列表
    │   │   ├── approval/            # 审批相关组件
    │   │   │   ├── ApprovalCard.tsx
    │   │   │   └── ApprovalTimeline.tsx
    │   │   ├── knowledge/           # 知识库组件
    │   │   │   ├── DocumentCard.tsx
    │   │   │   └── DocumentUploader.tsx
    │   │   ├── notifications/       # 通知组件
    │   │   │   └── NotificationItem.tsx
    │   │   ├── layout/              # 布局组件
    │   │   │   ├── Header.tsx
    │   │   │   ├── Sidebar.tsx
    │   │   │   └── PageLayout.tsx
    │   │   └── feedback/            # 反馈组件
    │   │       ├── ErrorBoundary.tsx
    │   │       └── LoadingState.tsx
    │   │
    │   ├── hooks/                   # 自定义 Hooks
    │   │   ├── useChat.ts           # 对话逻辑
    │   │   ├── useSSE.ts            # SSE 连接管理
    │   │   ├── useWebSocket.ts      # WebSocket 连接
    │   │   ├── useAuth.ts           # 认证状态
    │   │   ├── useTenant.ts         # 租户上下文
    │   │   ├── usePermission.ts     # 权限检查
    │   │   ├── useNetworkStatus.ts  # 网络状态检测
    │   │   ├── useDebounce.ts       # 防抖 Hook
    │   │   ├── useThrottle.ts       # 节流 Hook
    │   │   └── useLocalStorage.ts    # 本地存储 Hook
    │   │
    │   ├── services/                # API 调用层
    │   │   ├── api.ts               # Axios 实例配置
    │   │   ├── chat.ts              # 对话 API
    │   │   ├── session.ts           # 会话 API
    │   │   ├── approval.ts          # 审批 API
    │   │   ├── tools.ts             # 工具管理 API
    │   │   ├── audit.ts             # 审计 API
    │   │   ├── tenant.ts            # 租户 API
    │   │   └── dashboard.ts         # 监控 API
    │   │
    │   ├── stores/                  # Zustand 状态
    │   │   ├── authStore.ts         # 认证状态
    │   │   ├── chatStore.ts         # 对话状态
    │   │   ├── notificationStore.ts # 通知状态
    │   │   └── uiStore.ts           # UI 状态（侧边栏、主题）
    │   │
    │   ├── types/                   # TypeScript 类型定义
    │   │   ├── api.ts               # API 请求响应类型
    │   │   ├── chat.ts              # 对话相关类型
    │   │   ├── approval.ts          # 审批相关类型
    │   │   ├── tools.ts             # 工具相关类型
    │   │   ├── audit.ts             # 审计相关类型
    │   │   └── error.ts             # 错误码类型
    │   │
    │   ├── utils/                   # 工具函数
    │   │   ├── request.ts           # 请求封装
    │   │   ├── error.ts             # 错误处理
    │   │   ├── format.ts            # 格式化
    │   │   ├── date.ts              # 日期处理
    │   │   └── storage.ts           # 本地存储
    │   │
    │   ├── constants/               # 常量
    │   │   ├── routes.ts            # 路由常量
    │   │   ├── errorCodes.ts        # 错误码映射
    │   │   └── config.ts            # 配置常量
    │   │
    │   └── styles/                  # 全局样式
    │       ├── global.css           # 全局 CSS
    │       └── antd-overrides.css   # Ant Design 样式覆盖
    │
    ├── public/                      # 静态资源
    │   ├── favicon.ico
    │   └── logo.svg
    │
    ├── tests/                       # 测试
    │   ├── unit/                    # 单元测试
    │   └── e2e/                     # E2E 测试
    │
    └── scripts/                     # 脚本
        └── generate-types.ts        # 从 OpenAPI 生成类型
```

---

## 3. API 类型定义

> 与 [02-communication-contracts.md](./02-communication-contracts.md) 保持一致

### 3.1 通用类型

```typescript
// src/types/api.ts

/** 通用 Header（所有请求必须携带） */
export interface RequestHeader {
  'X-Request-ID': string;      // UUID v7
  'X-Tenant-ID': string;       // 租户标识
  'X-User-ID': string;         // 用户标识
  'X-Trace-ID': string;        // OpenTelemetry Trace ID
}

/** 分页请求 */
export interface PageRequest {
  page_number: number;         // 从 1 开始
  page_size: number;           // 1-100，默认 20
  sort_by?: string;
  sort_descending?: boolean;
}

/** 分页响应 */
export interface PageResponse<T> {
  items: T[];
  total_count: number;
  page_number: number;
  total_pages: number;
  has_next: boolean;
}

/** API 统一响应 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ErrorDetail;
  request_id: string;
  timestamp_ms: number;
}

/** 错误详情 */
export interface ErrorDetail {
  code: ErrorCode;
  message: string;             // 开发者信息（英文）
  user_message: string;        // 用户友好信息（中文）
  details?: Record<string, string>;
  request_id: string;
  trace_id: string;
  retry_after_seconds?: number;
}
```

### 3.2 错误码枚举

```typescript
// src/types/error.ts

/** 统一错误码（与后端 Protobuf ErrorCode 一致） */
export enum ErrorCode {
  // 通用错误 (10xxx)
  ERR_INVALID_REQUEST = 10001,
  ERR_UNAUTHORIZED = 10002,
  ERR_FORBIDDEN = 10003,
  ERR_RATE_LIMITED = 10004,
  ERR_TIMEOUT = 10005,
  ERR_SERVICE_UNAVAILABLE = 10006,
  ERR_METHOD_NOT_ALLOWED = 10007,
  ERR_RESOURCE_NOT_FOUND = 10008,
  ERR_CONFLICT = 10009,

  // Agent 编排错误 (20xxx)
  ERR_AGENT_MAX_STEPS_EXCEEDED = 20001,
  ERR_AGENT_CONTEXT_TOO_LONG = 20002,
  ERR_AGENT_TOOL_NOT_FOUND = 20003,
  ERR_AGENT_RUN_CANCELLED = 20004,
  ERR_AGENT_RUN_PAUSED = 20005,

  // 模型网关错误 (30xxx)
  ERR_MODEL_ALL_PROVIDERS_DOWN = 30001,
  ERR_MODEL_TOKEN_LIMIT = 30002,
  ERR_MODEL_CONTENT_FILTERED = 30003,
  ERR_MODEL_UNSUPPORTED_OPERATION = 30004,
  ERR_MODEL_QUOTA_EXCEEDED = 30005,

  // 工具总线错误 (40xxx)
  ERR_TOOL_VALIDATION_FAILED = 40001,
  ERR_TOOL_EXECUTION_FAILED = 40002,
  ERR_TOOL_RISK_REJECTED = 40003,
  ERR_TOOL_APPROVAL_REQUIRED = 40004,
  ERR_TOOL_TIMEOUT = 40005,
  ERR_TOOL_DISABLED = 40006,

  // 风控错误 (50xxx)
  ERR_RISK_BLOCKED = 50001,
  ERR_RISK_SUSPICIOUS_BEHAVIOR = 50002,

  // 审批错误 (60xxx)
  ERR_APPROVAL_EXPIRED = 60001,
  ERR_APPROVAL_ALREADY_REVIEWED = 60002,
  ERR_APPROVAL_NOT_ASSIGNEE = 60003,

  // 知识库错误 (70xxx)
  ERR_KNOWLEDGE_DOCUMENT_NOT_FOUND = 70001,
  ERR_KNOWLEDGE_INDEX_FAILED = 70002,
}

/** 错误码分类 */
export const ErrorCodeCategory = {
  GENERAL: [10000, 19999],
  AGENT: [20000, 29999],
  MODEL: [30000, 39999],
  TOOL: [40000, 49999],
  RISK: [50000, 59999],
  APPROVAL: [60000, 69999],
  KNOWLEDGE: [70000, 79999],
} as const;

/** 判断是否可重试 */
export function isRetryable(code: ErrorCode): boolean {
  return [
    ErrorCode.ERR_TIMEOUT,
    ErrorCode.ERR_RATE_LIMITED,
    ErrorCode.ERR_SERVICE_UNAVAILABLE,
    ErrorCode.ERR_MODEL_ALL_PROVIDERS_DOWN,
  ].includes(code);
}
```

### 3.3 对话相关类型

```typescript
// src/types/chat.ts

/** 对话请求 */
export interface ChatRequest {
  message: string;
  session_id?: string;
  history?: MessageHistory[];
  options?: AgentOptions;
}

/** 历史消息 */
export interface MessageHistory {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

/** Agent 选项 */
export interface AgentOptions {
  temperature?: number;
  max_tokens?: number;
  stream?: boolean;              // 默认 true
  enabled_tools?: string[];      // 白名单工具
  model_override?: string;       // 强制指定模型
}

/** SSE 流式响应块 */
export interface ChatCompletionChunk {
  chunk_id: string;
  delta_content: string;         // 增量文本
  is_final: boolean;
  finish_reason: FinishReason;
  usage?: TokenUsage;
  step_info?: AgentStepInfo;
}

export type FinishReason = 'stop' | 'tool_call' | 'length' | 'error';

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

/** Agent 步骤信息（用于可视化） */
export interface AgentStepInfo {
  step_order: number;
  step_type: StepType;
  step_name?: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  tool_name?: string;
  thinking?: string;             // CoT 推理过程
}

export type StepType = 
  | 'thinking'
  | 'tool_call'
  | 'observation'
  | 'final_answer'
  | 'intent_classify'
  | 'retrieve'
  | 'risk_check'
  | 'approval_wait';

/** 会话 */
export interface Session {
  id: string;
  tenant_id: string;
  user_id: string;
  session_type: 'chat' | 'task' | 'workflow';
  title?: string;
  status: 'active' | 'archived' | 'closed';
  created_at: string;
  updated_at: string;
}

/** Agent 运行 */
export interface AgentRun {
  id: string;
  session_id: string;
  tenant_id: string;
  user_id: string;
  run_number: number;
  input_message: string;
  output_message?: string;
  status: RunStatus;
  error_message?: string;
  error_code?: ErrorCode;
  model_used?: string;
  total_tokens: number;
  total_cost_usd: number;
  duration_ms?: number;
  started_at: string;
  completed_at?: string;
}

export type RunStatus = 
  | 'pending'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled';

/** 执行步骤 */
export interface AgentStep {
  id: string;
  run_id: string;
  step_order: number;
  step_type: StepType;
  content: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: Record<string, unknown>;
  thinking?: string;
  token_count: number;
  duration_ms?: number;
  created_at: string;
}
```

### 3.4 审批相关类型

```typescript
// src/types/approval.ts

/** 审批任务 */
export interface ApprovalTask {
  id: string;
  run_id: string;
  tool_invocation_id?: string;
  tenant_id: string;
  task_type: ApprovalType;
  title: string;
  description: string;
  request_context: Record<string, unknown>;  // 待审批内容快照
  requester_id: string;
  assignee_id?: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  status: ApprovalStatus;
  reviewer_id?: string;
  review_comment?: string;
  reviewed_at?: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export type ApprovalType = 
  | 'tool_approval'
  | 'sensitive_action'
  | 'high_value_transaction';

export type ApprovalStatus = 
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'expired'
  | 'cancelled';

/** 审批操作请求 */
export interface ApprovalActionRequest {
  comment?: string;
}

/** 审批通知（WebSocket 推送） */
export interface ApprovalNotification {
  event_type: 'approval.created' | 'approval.approved' | 'approval.rejected' | 'approval.expired';
  approval_id: string;
  title: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  created_at: string;
}
```

### 3.5 工具管理类型

```typescript
// src/types/tools.ts

/** 工具定义 */
export interface ToolDefinition {
  name: string;
  description: string;
  version: string;
  category: 'query' | 'write' | 'external';
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  parameters: JSONSchema;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  auth_type: 'service_token' | 'oauth2' | 'api_key' | 'none';
  timeout_ms: number;
  allowed_roles: ('admin' | 'operator' | 'viewer')[];
  daily_quota_per_user?: number;
  tags: string[];
  owner_team?: string;
  enabled: boolean;
  status: ToolStatus;
  created_at: string;
  updated_at: string;
}

export type ToolStatus = 'draft' | 'active' | 'disabled' | 'deprecated' | 'sunset';

/** JSON Schema（工具参数定义） */
export interface JSONSchema {
  type: string;
  properties?: Record<string, JSONSchema>;
  required?: string[];
  description?: string;
  [key: string]: unknown;
}

/** 工具注册请求 */
export interface ToolRegisterRequest {
  name: string;
  description: string;
  version: string;
  category: 'query' | 'write' | 'external';
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  parameters: JSONSchema;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  auth_type: 'service_token' | 'oauth2' | 'api_key' | 'none';
  timeout_ms: number;
  allowed_roles: ('admin' | 'operator' | 'viewer')[];
  daily_quota_per_user?: number;
  tags?: string[];
  owner_team?: string;
  enabled?: boolean;
}

/** 工具调用记录 */
export interface ToolInvocation {
  id: string;
  step_id: string;
  run_id: string;
  tool_name: string;
  tool_category: 'query' | 'write' | 'external';
  tool_version: string;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  input_data: Record<string, unknown>;
  output_data?: Record<string, unknown>;
  status: 'pending' | 'success' | 'failed' | 'rejected' | 'timeout';
  error_code?: ErrorCode;
  error_message?: string;
  approval_id?: string;
  was_cached: boolean;
  duration_ms?: number;
  provider_latency_ms?: number;
  created_at: string;
  completed_at?: string;
}
```

### 3.6 审计相关类型

```typescript
// src/types/audit.ts

/** 审计事件 */
export interface AuditEvent {
  id: number;
  event_id: string;
  event_type: string;
  event_category: 'lifecycle' | 'security' | 'business' | 'system';
  severity: 'info' | 'warn' | 'error' | 'critical';
  tenant_id: string;
  user_id: string;
  resource_type?: string;
  resource_id?: string;
  action: string;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  details?: Record<string, unknown>;
  request_id: string;
  trace_id: string;
  ip_address?: string;
  user_agent?: string;
  source_service: string;
  created_at: string;
}

/** 审计查询参数 */
export interface AuditQueryParams extends PageRequest {
  event_type?: string;
  event_category?: string;
  severity?: string;
  user_id?: string;
  resource_type?: string;
  resource_id?: string;
  start_time?: string;
  end_time?: string;
}
```

---

## 4. 认证与权限

> 与 [03-security-specification.md](./03-security-specification.md) 保持一致

### 4.1 JWT 认证流程

```typescript
// src/stores/authStore.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  tenant: Tenant | null;
  isAuthenticated: boolean;
  
  // Actions
  login: (tokens: TokenPair, user: User, tenant: Tenant) => void;
  logout: () => void;
  refreshTokens: (tokens: TokenPair) => void;
  updateUser: (user: Partial<User>) => void;
}

export interface User {
  id: string;
  username: string;
  email: string;
  roles: Role[];
  permissions: string[];
}

export type Role = 'admin' | 'operator' | 'viewer';

export interface Tenant {
  id: string;
  name: string;
  tier: 'free' | 'standard' | 'premium' | 'enterprise';
  features: string[];
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      tenant: null,
      isAuthenticated: false,

      login: (tokens, user, tenant) => {
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          user,
          tenant,
          isAuthenticated: true,
        });
      },

      logout: () => {
        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          tenant: null,
          isAuthenticated: false,
        });
        // 清除其他 store
        localStorage.clear();
      },

      refreshTokens: (tokens) => {
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
        });
      },

      updateUser: (userData) => {
        const { user } = get();
        if (user) {
          set({ user: { ...user, ...userData } });
        }
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        tenant: state.tenant,
      }),
    }
  )
);
```

### 4.2 状态管理完整定义

#### chatStore - 对话状态（含离线支持）

```typescript
// src/stores/chatStore.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  is_offline?: boolean; // 离线创建标记
}

export interface PendingMessage {
  id: string;
  session_id: string;
  content: string;
  created_at: string;
  retry_count: number;
}

export interface ChatState {
  // 会话数据
  messages: Message[];
  pendingQueue: PendingMessage[]; // 离线待发送队列
  
  // UI 状态
  currentSessionId: string | null;
  isOnline: boolean;
  
  // Actions
  addMessage: (message: Message) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  deleteMessage: (id: string) => void;
  
  // 离线支持
  addToPendingQueue: (message: PendingMessage) => void;
  removeFromPendingQueue: (id: string) => void;
  retryPendingMessages: () => Promise<void>;
  
  // 会话管理
  setCurrentSession: (sessionId: string | null) => void;
  clearSession: (sessionId: string) => void;
  setOnline: (status: boolean) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      pendingQueue: [],
      currentSessionId: null,
      isOnline: navigator.onLine,
      
      addMessage: (message) => {
        set((state) => ({
          messages: [...state.messages, message],
        }));
      },
      
      updateMessage: (id, updates) => {
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === id ? { ...m, ...updates } : m
          ),
        }));
      },
      
      deleteMessage: (id) => {
        set((state) => ({
          messages: state.messages.filter((m) => m.id !== id),
        }));
      },
      
      addToPendingQueue: (message) => {
        set((state) => ({
          pendingQueue: [...state.pendingQueue, message],
        }));
      },
      
      removeFromPendingQueue: (id) => {
        set((state) => ({
          pendingQueue: state.pendingQueue.filter((m) => m.id !== id),
        }));
      },
      
      retryPendingMessages: async () => {
        const { pendingQueue, addMessage, removeFromPendingQueue } = get();
        
        for (const pending of pendingQueue) {
          if (pending.retry_count >= 3) {
            console.warn('Max retries exceeded for message:', pending.id);
            continue;
          }
          
          try {
            // 调用 API 发送消息
            const response = await fetch('/api/v1/chat/completions', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                message: pending.content,
                session_id: pending.session_id,
              }),
            });
            
            if (response.ok) {
              // 标记为已发送
              addMessage({
                id: pending.id,
                session_id: pending.session_id,
                role: 'user',
                content: pending.content,
                created_at: pending.created_at,
                is_offline: false,
              });
              removeFromPendingQueue(pending.id);
            } else {
              throw new Error('Failed to send');
            }
          } catch (error) {
            console.error('Failed to retry message:', pending.id, error);
            // 更新重试计数
            set((state) => ({
              pendingQueue: state.pendingQueue.map((m) =>
                m.id === pending.id 
                  ? { ...m, retry_count: m.retry_count + 1 }
                  : m
              ),
            }));
          }
        }
      },
      
      setCurrentSession: (sessionId) => {
        set({ currentSessionId: sessionId });
      },
      
      clearSession: (sessionId) => {
        set((state) => ({
          messages: state.messages.filter((m) => m.session_id !== sessionId),
        }));
      },
      
      setOnline: (status) => {
        const wasOffline = !get().isOnline;
        set({ isOnline: status });
        
        // 网络恢复时自动重试
        if (wasOffline && status) {
          get().retryPendingMessages();
        }
      },
    }),
    {
      name: 'chat-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        messages: state.messages.slice(-100), // 只保留最近100条
        pendingQueue: state.pendingQueue,
      }),
    }
  )
);

// 网络状态监听（入口文件初始化）
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    useChatStore.getState().setOnline(true);
  });
  window.addEventListener('offline', () => {
    useChatStore.getState().setOnline(false);
  });
}
```

### 4.3 RBAC 权限检查

```typescript
// src/hooks/usePermission.ts

import { useAuthStore } from '@/stores/authStore';

/** 权限定义 */
export const Permissions = {
  // 对话
  CHAT_READ: 'chat:read',
  CHAT_WRITE: 'chat:write',
  
  // 审批
  APPROVAL_READ: 'approval:read',
  APPROVAL_APPROVE: 'approval:approve',
  APPROVAL_REJECT: 'approval:reject',
  
  // 工具管理
  TOOL_READ: 'tool:read',
  TOOL_WRITE: 'tool:write',
  TOOL_DELETE: 'tool:delete',
  
  // 审计
  AUDIT_READ: 'audit:read',
  AUDIT_EXPORT: 'audit:export',
  
  // 租户
  TENANT_READ: 'tenant:read',
  TENANT_WRITE: 'tenant:write',
  
  // 监控
  DASHBOARD_READ: 'dashboard:read',
} as const;

/** 角色权限映射 */
export const RolePermissions: Record<Role, string[]> = {
  admin: Object.values(Permissions),
  operator: [
    Permissions.CHAT_READ,
    Permissions.CHAT_WRITE,
    Permissions.APPROVAL_READ,
    Permissions.APPROVAL_APPROVE,
    Permissions.APPROVAL_REJECT,
    Permissions.TOOL_READ,
    Permissions.AUDIT_READ,
    Permissions.DASHBOARD_READ,
  ],
  viewer: [
    Permissions.CHAT_READ,
    Permissions.APPROVAL_READ,
    Permissions.TOOL_READ,
    Permissions.AUDIT_READ,
    Permissions.DASHBOARD_READ,
  ],
};

/** 检查是否有权限 */
export function usePermission() {
  const user = useAuthStore((state) => state.user);
  
  const hasPermission = (permission: string): boolean => {
    if (!user) return false;
    
    // 检查用户直接权限
    if (user.permissions.includes(permission)) return true;
    
    // 检查角色权限
    return user.roles.some((role) => 
      RolePermissions[role]?.includes(permission)
    );
  };
  
  const hasAnyPermission = (permissions: string[]): boolean => {
    return permissions.some(hasPermission);
  };
  
  const hasAllPermissions = (permissions: string[]): boolean => {
    return permissions.every(hasPermission);
  };
  
  const hasRole = (role: Role): boolean => {
    return user?.roles.includes(role) ?? false;
  };
  
  return {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    hasRole,
  };
}
```

### 4.3 路由守卫

```typescript
// src/routes/__root.tsx

import { createRootRoute, Outlet, redirect } from '@tanstack/react-router';
import { useAuthStore } from '@/stores/authStore';
import { PageLayout } from '@/components/layout/PageLayout';

export const Route = createRootRoute({
  component: RootComponent,
  beforeLoad: async ({ location }) => {
    const { isAuthenticated, accessToken } = useAuthStore.getState();
    
    // 未登录且不在登录页，重定向到登录
    if (!isAuthenticated && !accessToken) {
      if (location.pathname !== '/login') {
        throw redirect({
          to: '/login',
          search: { redirect: location.href },
        });
      }
    }
    
    // 已登录但在登录页，重定向到首页
    if (isAuthenticated && location.pathname === '/login') {
      throw redirect({ to: '/' });
    }
  },
});

function RootComponent() {
  return (
    <PageLayout>
      <Outlet />
    </PageLayout>
  );
}
```

```typescript
// src/routes/tools/index.tsx - 权限保护示例

import { createFileRoute, redirect } from '@tanstack/react-router';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { ToolsList } from '@/components/tools/ToolsList';

export const Route = createFileRoute('/tools/')({
  component: ToolsPage,
  beforeLoad: async () => {
    const { hasPermission } = usePermission();
    
    if (!hasPermission(Permissions.TOOL_READ)) {
      throw redirect({ to: '/forbidden' });
    }
  },
});

function ToolsPage() {
  return <ToolsList />;
}
```

### 4.4 多租户上下文注入

```typescript
// src/services/api.ts

import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/stores/authStore';
import { generateRequestId } from '@/utils/request';

const api: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/** 请求拦截器：注入认证和多租户 Header */
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { accessToken, user, tenant } = useAuthStore.getState();
    
    // JWT Token
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    
    // 多租户 Header
    if (tenant) {
      config.headers['X-Tenant-ID'] = tenant.id;
    }
    
    if (user) {
      config.headers['X-User-ID'] = user.id;
    }
    
    // 请求追踪
    config.headers['X-Request-ID'] = generateRequestId();
    config.headers['X-Trace-ID'] = config.headers['X-Request-ID'];
    
    return config;
  },
  (error) => Promise.reject(error)
);

/** 响应拦截器：处理错误和 Token 刷新 */
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Token 过期，尝试刷新
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const { refreshToken } = useAuthStore.getState();
        const { data } = await axios.post('/auth/refresh', {
          refresh_token: refreshToken,
        });
        
        useAuthStore.getState().refreshTokens(data);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        
        return api(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().logout();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export default api;
```

### 4.5 安全加固

#### 敏感信息加密存储

> **安全红线**：Token 存储必须加密，禁止明文存储敏感信息。

```typescript
// src/utils/crypto.ts

const ENCRYPTION_KEY = import.meta.env.VITE_STORAGE_KEY;

/** 简单 XOR 加密（生产环境建议使用 Web Crypto API + AES） */
export function encrypt(text: string): string {
  if (!ENCRYPTION_KEY) return text;
  const key = ENCRYPTION_KEY.padEnd(text.length, ENCRYPTION_KEY);
  return btoa(
    text.split('').map((char, i) => 
      String.fromCharCode(char.charCodeAt(0) ^ key.charCodeAt(i))
    ).join('')
  );
}

export function decrypt(ciphertext: string): string {
  if (!ENCRYPTION_KEY) return ciphertext;
  const key = ENCRYPTION_KEY.padEnd(ciphertext.length, ENCRYPTION_KEY);
  const text = atob(ciphertext);
  return text.split('').map((char, i) => 
    String.fromCharCode(char.charCodeAt(0) ^ key.charCodeAt(i))
  ).join('');
}

// src/stores/authStore.ts 修改
import { encrypt, decrypt } from '@/utils/crypto';

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({ /* ... */ }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => ({
        getItem: (name) => {
          const encrypted = localStorage.getItem(name);
          return encrypted ? decrypt(encrypted) : null;
        },
        setItem: (name, value) => {
          localStorage.setItem(name, encrypt(value));
        },
        removeItem: (name) => localStorage.removeItem(name),
      })),
    }
  )
);
```

#### WebSocket 安全认证

> **禁止**：WebSocket URL 参数传递 Token（存在泄露风险）

```typescript
// src/hooks/useWebSocket.ts

import { useEffect, useRef, useState, useCallback } from 'react';
import { useAuthStore } from '@/stores/authStore';

export interface WebSocketOptions<T> {
  url: string;
  onMessage: (data: T) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  heartbeatInterval?: number;
}

export interface WebSocketState {
  isConnected: boolean;
  isReconnecting: boolean;
  error: Event | null;
}

export function useWebSocket<T = unknown>(options: WebSocketOptions<T>) {
  const {
    url,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectDelay = 3000,
    heartbeatInterval = 30000,
  } = options;
  
  const { accessToken } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);
  
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isReconnecting: false,
    error: null,
  });
  
  // 心跳检测
  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, heartbeatInterval);
  }, [heartbeatInterval]);
  
  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);
  
  // 连接
  const connect = useCallback(() => {
    if (!accessToken) return;
    
    const ws = new WebSocket(url);
    wsRef.current = ws;
    
    ws.onopen = () => {
      // 发送认证消息
      ws.send(JSON.stringify({
        type: 'auth',
        token: accessToken,
      }));
      
      setState({ isConnected: true, isReconnecting: false, error: null });
      reconnectCountRef.current = 0;
      startHeartbeat();
      onConnect?.();
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // 忽略心跳响应
        if (data.type === 'pong') return;
        
        onMessage(data);
      } catch (e) {
        console.warn('Failed to parse WebSocket message:', event.data);
      }
    };
    
    ws.onerror = (error) => {
      setState((s) => ({ ...s, error }));
      onError?.(error);
    };
    
    ws.onclose = (event) => {
      stopHeartbeat();
      setState((s) => ({ ...s, isConnected: false }));
      onDisconnect?.();
      
      // 非正常关闭，尝试重连
      if (event.code !== 1000 && reconnectCountRef.current < reconnectAttempts) {
        reconnectCountRef.current += 1;
        setState((s) => ({ ...s, isReconnecting: true }));
        
        const delay = reconnectDelay * Math.pow(1.5, reconnectCountRef.current - 1);
        reconnectTimerRef.current = setTimeout(connect, delay);
      }
    };
  }, [url, accessToken, onMessage, onConnect, onDisconnect, onError, reconnectAttempts, reconnectDelay, startHeartbeat, stopHeartbeat]);
  
  // 断开连接
  const disconnect = useCallback(() => {
    stopHeartbeat();
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000); // 正常关闭
      wsRef.current = null;
    }
    setState({ isConnected: false, isReconnecting: false, error: null });
  }, [stopHeartbeat]);
  
  // 发送消息
  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);
  
  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);
  
  return {
    ...state,
    send,
    disconnect,
    reconnect: () => {
      reconnectCountRef.current = 0;
      connect();
    },
  };
}
```

#### Token 主动过期检测

```typescript
// src/stores/authStore.ts 补充

// Token 过期前 60 秒自动刷新
useEffect(() => {
  const { accessToken, expiresAt } = useAuthStore.getState();
  if (!expiresAt) return;
  
  const now = Date.now();
  const refreshTime = expiresAt - 60000; // 提前 1 分钟
  
  if (refreshTime <= now) {
    // 已接近过期，立即刷新
    refreshToken();
  } else {
    // 定时刷新
    const timer = setTimeout(refreshToken, refreshTime - now);
    return () => clearTimeout(timer);
  }
}, []);
```

---

## 5. SSE 流式通信

> 与 [05-performance-optimization.md](./05-performance-optimization.md) Fast Path 设计一致

### 5.1 SSE Hook 实现

> **安全说明**：使用 Fetch + ReadableStream 替代原生 EventSource，支持 POST 请求和自定义 Header（JWT Token），避免 URL 参数泄露风险。

```typescript
// src/hooks/useSSE.ts

import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';

export interface SSEOptions<T> {
  url: string;
  body?: Record<string, unknown>;
  onMessage: (data: T) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
  enabled?: boolean;
  retryAttempts?: number;
  retryDelay?: number;
}

export interface SSEState {
  isConnected: boolean;
  isStreaming: boolean;
  error: Error | null;
  retryCount: number;
}

/** 完整 SSE 消息解析 */
interface SSEMessage {
  event?: string;
  id?: string;
  data: string;
}

function parseSSEMessages(chunk: string, buffer: string): { messages: SSEMessage[]; remaining: string } {
  const messages: SSEMessage[] = [];
  const fullText = buffer + chunk;
  const lines = fullText.split('\n');
  let current: Partial<SSEMessage> = {};
  const remainingLines: string[] = [];
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // 空行表示消息结束
    if (line === '') {
      if (current.data !== undefined) {
        messages.push(current as SSEMessage);
      }
      current = {};
    } else if (line.startsWith('event:')) {
      current.event = line.slice(6).trim();
    } else if (line.startsWith('id:')) {
      current.id = line.slice(3).trim();
    } else if (line.startsWith('data:')) {
      // 支持多行 data 累加
      current.data = (current.data || '') + line.slice(5);
    } else if (i === lines.length - 1 && !line.endsWith('\n')) {
      // 未完成的行，保留到下次处理
      remainingLines.push(line);
    }
  }
  
  return { messages, remaining: remainingLines.join('\n') };
}

export function useSSE<T = unknown>(options: SSEOptions<T>) {
  const {
    url,
    body,
    onMessage,
    onError,
    onComplete,
    enabled = true,
    retryAttempts = 3,
    retryDelay = 1000,
  } = options;
  
  const abortControllerRef = useRef<AbortController | null>(null);
  const bufferRef = useRef<string>('');
  const lastEventIdRef = useRef<string>('');
  const retryCountRef = useRef(0);
  
  const [state, setState] = useState<SSEState>({
    isConnected: false,
    isStreaming: false,
    error: null,
    retryCount: 0,
  });
  
  const connect = useCallback(() => {
    if (!enabled) return;
    
    const { accessToken, tenant, user } = useAuthStore.getState();
    
    abortControllerRef.current = new AbortController();
    bufferRef.current = '';
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
      'X-Tenant-ID': tenant?.id || '',
      'X-User-ID': user?.id || '',
      Accept: 'text/event-stream',
    };
    
    // 重连时携带 Last-Event-ID
    if (lastEventIdRef.current) {
      headers['Last-Event-ID'] = lastEventIdRef.current;
    }
    
    fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: abortControllerRef.current.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        
        setState((s) => ({ ...s, isConnected: true, isStreaming: true, error: null }));
        
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        
        const readChunk = (): Promise<void> | undefined => {
          return reader?.read().then(({ done, value }) => {
            if (done) {
              setState((s) => ({ ...s, isStreaming: false }));
              onComplete?.();
              return;
            }
            
            const chunk = decoder.decode(value, { stream: true });
            const { messages, remaining } = parseSSEMessages(chunk, bufferRef.current);
            bufferRef.current = remaining;
            
            for (const msg of messages) {
              // 记录最后事件 ID（用于重连恢复）
              if (msg.id) {
                lastEventIdRef.current = msg.id;
              }
              
              // 处理心跳事件
              if (msg.event === 'heartbeat') {
                continue;
              }
              
              // 解析业务数据
              try {
                const data = JSON.parse(msg.data) as T;
                onMessage(data);
              } catch (e) {
                console.warn('Failed to parse SSE message:', msg.data, e);
              }
            }
            
            return readChunk();
          });
        };
        
        return readChunk();
      })
      .catch((error) => {
        if (error.name === 'AbortError') {
          // 用户主动取消，不算错误
          setState((s) => ({ ...s, isStreaming: false }));
          return;
        }
        
        setState((s) => ({ ...s, error, isStreaming: false }));
        onError?.(error);
        
        // 自动重试（指数退避）
        if (retryCountRef.current < retryAttempts) {
          retryCountRef.current += 1;
          setState((s) => ({ ...s, retryCount: retryCountRef.current }));
          const delay = retryDelay * Math.pow(2, retryCountRef.current - 1);
          setTimeout(connect, delay);
        }
      });
  }, [url, body, enabled, onMessage, onError, onComplete, retryAttempts, retryDelay]);
  
  const disconnect = useCallback(() => {
    abortControllerRef.current?.abort();
    setState((s) => ({ ...s, isConnected: false, isStreaming: false }));
  }, []);
  
  useEffect(() => {
    if (enabled) {
      connect();
    }
    return disconnect;
  }, [enabled, connect, disconnect]);
  
  return {
    ...state,
    connect,
    disconnect,
    retry: () => {
      retryCountRef.current = 0;
      lastEventIdRef.current = '';
      setState((s) => ({ ...s, retryCount: 0, error: null }));
      connect();
    },
  };
}
```

### 5.2 对话 Hook

```typescript
// src/hooks/useChat.ts

import { useState, useCallback, useRef } from 'react';
import { useSSE } from './useSSE';
import { useChatStore } from '@/stores/chatStore';
import type { ChatCompletionChunk, ChatRequest, AgentStepInfo } from '@/types/chat';

export interface UseChatOptions {
  sessionId?: string;
  onComplete?: (message: string) => void;
  onError?: (error: Error) => void;
}

export function useChat(options: UseChatOptions = {}) {
  const { sessionId, onComplete, onError } = options;
  
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentMessage, setCurrentMessage] = useState('');
  const [steps, setSteps] = useState<AgentStepInfo[]>([]);
  const [usage, setUsage] = useState<{ prompt: number; completion: number } | null>(null);
  
  const messageRef = useRef('');
  const abortControllerRef = useRef<AbortController | null>(null);
  
  const sendMessage = useCallback(async (request: ChatRequest) => {
    setIsStreaming(true);
    setCurrentMessage('');
    setSteps([]);
    setUsage(null);
    messageRef.current = '';
    
    abortControllerRef.current = new AbortController();
    
    const { accessToken, tenant, user } = useAuthStore.getState();
    
    try {
      const response = await fetch('/api/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
          'X-Tenant-ID': tenant?.id || '',
          'X-User-ID': user?.id || '',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({
          ...request,
          session_id: sessionId,
          options: {
            ...request.options,
            stream: true,
          },
        }),
        signal: abortControllerRef.current.signal,
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: ChatCompletionChunk = JSON.parse(line.slice(6));
              
              // 累加内容
              messageRef.current += data.delta_content;
              setCurrentMessage(messageRef.current);
              
              // 更新步骤信息
              if (data.step_info) {
                setSteps((prev) => {
                  const existing = prev.findIndex(
                    (s) => s.step_order === data.step_info!.step_order
                  );
                  if (existing >= 0) {
                    const updated = [...prev];
                    updated[existing] = data.step_info!;
                    return updated;
                  }
                  return [...prev, data.step_info!];
                });
              }
              
              // 更新 token 用量
              if (data.usage) {
                setUsage({
                  prompt: data.usage.prompt_tokens,
                  completion: data.usage.completion_tokens,
                });
              }
              
              // 完成
              if (data.is_final) {
                setIsStreaming(false);
                onComplete?.(messageRef.current);
              }
            } catch (e) {
              console.error('Failed to parse SSE chunk:', e);
            }
          }
        }
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        // 用户取消
        setIsStreaming(false);
        return;
      }
      
      setIsStreaming(false);
      onError?.(error as Error);
    }
  }, [sessionId, onComplete, onError]);
  
  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
  }, []);
  
  return {
    sendMessage,
    cancel,
    isStreaming,
    currentMessage,
    steps,
    usage,
  };
}
```

### 5.3 步骤可视化组件

```tsx
// src/components/chat/StepVisualizer.tsx

import { LucideIcon, Brain, Wrench, Eye, CheckCircle, XCircle, Clock } from 'lucide-react';
import type { AgentStepInfo, StepType } from '@/types/chat';

const StepIcons: Record<StepType, LucideIcon> = {
  thinking: Brain,
  tool_call: Wrench,
  observation: Eye,
  final_answer: CheckCircle,
  intent_classify: Brain,
  retrieve: Eye,
  risk_check: CheckCircle,
  approval_wait: Clock,
};

const StepLabels: Record<StepType, string> = {
  thinking: '思考中',
  tool_call: '调用工具',
  observation: '观察结果',
  final_answer: '最终回答',
  intent_classify: '意图分类',
  retrieve: '检索知识',
  risk_check: '风险检查',
  approval_wait: '等待审批',
};

interface StepVisualizerProps {
  steps: AgentStepInfo[];
  currentStep?: number;
}

export function StepVisualizer({ steps, currentStep }: StepVisualizerProps) {
  if (steps.length === 0) return null;
  
  return (
    <div className="flex flex-col gap-2 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
      <div className="text-sm font-medium text-gray-600 dark:text-gray-400">
        执行步骤
      </div>
      <div className="flex flex-wrap gap-2">
        {steps.map((step) => {
          const Icon = StepIcons[step.step_type];
          const isActive = step.status === 'running';
          const isComplete = step.status === 'completed';
          const isFailed = step.status === 'failed';
          
          return (
            <div
              key={step.step_order}
              className={`
                flex items-center gap-2 px-3 py-1.5 rounded-full text-sm
                ${isActive ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' : ''}
                ${isComplete ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' : ''}
                ${isFailed ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300' : ''}
                ${!isActive && !isComplete && !isFailed ? 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400' : ''}
              `}
            >
              <Icon className="w-4 h-4" />
              <span>{StepLabels[step.step_type]}</span>
              {step.tool_name && (
                <span className="text-xs opacity-70">({step.tool_name})</span>
              )}
              {isActive && (
                <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

---

## 6. 核心模块设计

### 6.0 性能优化策略

#### 代码分割

```typescript
// src/routes/__root.tsx
import { lazy, Suspense } from 'react';
import { LoadingState } from '@/components/feedback/LoadingState';

// 按路由懒加载
const DashboardPage = lazy(() => import('./dashboard/index'));
const ApprovalPage = lazy(() => import('./approval/index'));
const ToolsPage = lazy(() => import('./tools/index'));

// 图表组件懒加载（echarts 体积大）
const LazyChart = lazy(() => import('echarts-for-react').then(m => ({ default: m.default })));

// 使用示例
<Suspense fallback={<LoadingState />}>
  <DashboardPage />
</Suspense>
```

```typescript
// vite.config.ts 代码分割配置
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-router': ['@tanstack/react-router', '@tanstack/react-query'],
          'vendor-antd': ['antd', '@ant-design/icons'],
          'vendor-chart': ['echarts', 'echarts-for-react'],
        },
      },
    },
  },
});
```

#### 图片/资源优化

```typescript
// 图片懒加载组件
export function LazyImage({ src, alt }: { src: string; alt: string }) {
  const [isLoaded, setIsLoaded] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);
  
  useEffect(() => {
    if (!imgRef.current) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        imgRef.current!.src = src;
        observer.disconnect();
      }
    });
    observer.observe(imgRef.current);
    return () => observer.disconnect();
  }, [src]);
  
  return <img ref={imgRef} alt={alt} className={isLoaded ? '' : 'blur-sm'} />;
}
```

#### TanStack Query 缓存配置

```typescript
// src/main.tsx - QueryClient 配置
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,        // 5 分钟内数据视为新鲜
      gcTime: 30 * 60 * 1000,          // 30 分钟后清理缓存
      retry: 2,                         // 失败重试 2 次
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 30000),
      refetchOnWindowFocus: false,      // 窗口聚焦不自动刷新
      refetchOnReconnect: true,         // 网络重连时刷新
    },
    mutations: {
      retry: 1,                         // 变更操作重试 1 次
    },
  },
});

// 针对不同数据的缓存策略
export const queryConfigs = {
  // 静态数据：长缓存
  static: {
    staleTime: Infinity,
    gcTime: Infinity,
  },
  // 用户相关：中等缓存
  user: {
    staleTime: 2 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  },
  // 实时数据：短缓存
  realtime: {
    staleTime: 30 * 1000,
    gcTime: 5 * 60 * 1000,
  },
  // 不缓存
  noCache: {
    staleTime: 0,
    gcTime: 0,
  },
};

// 使用示例
const { data: tools } = useQuery({
  queryKey: ['tools'],
  queryFn: fetchTools,
  ...queryConfigs.user,
});

const { data: dashboard } = useQuery({
  queryKey: ['dashboard'],
  queryFn: fetchDashboard,
  ...queryConfigs.realtime,
  refetchInterval: 60000, // 每分钟刷新
});
```

#### 请求取消与并发控制

```typescript
// src/services/api.ts - 请求取消
const pendingRequests = new Map<string, AbortController>();

// 生成请求唯一标识
function generateRequestKey(config: InternalAxiosRequestConfig): string {
  return `${config.method}:${config.url}:${JSON.stringify(config.params)}`;
}

// 请求拦截器：支持取消重复请求
api.interceptors.request.use((config) => {
  const key = generateRequestKey(config);
  
  // 取消之前的相同请求
  if (pendingRequests.has(key)) {
    pendingRequests.get(key)?.abort();
  }
  
  const controller = new AbortController();
  config.signal = controller.signal;
  pendingRequests.set(key, controller);
  
  return config;
});

// 响应拦截器：清理请求
api.interceptors.response.use(
  (response) => {
    const key = generateRequestKey(response.config);
    pendingRequests.delete(key);
    return response;
  },
  (error) => {
    if (error.config) {
      const key = generateRequestKey(error.config);
      pendingRequests.delete(key);
    }
    return Promise.reject(error);
  }
);

// 批量请求控制
export async function batchRequests<T>(
  requests: (() => Promise<T>)[],
  concurrency: number = 5
): Promise<T[]> {
  const results: T[] = [];
  const queue = [...requests];
  
  async function processQueue(): Promise<void> {
    while (queue.length > 0) {
      const request = queue.shift();
      if (request) {
        const result = await request();
        results.push(result);
      }
    }
  }
  
  await Promise.all(Array(concurrency).fill(null).map(processQueue));
  return results;
}
  
  useEffect(() => {
    if (!imgRef.current) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        imgRef.current!.src = src;
        observer.disconnect();
      }
    });
    observer.observe(imgRef.current);
    return () => observer.disconnect();
  }, [src]);
  
  return <img ref={imgRef} alt={alt} className={isLoaded ? '' : 'blur-sm'} />;
}
```

### 6.1 对话界面

```tsx
// src/routes/chat/$sessionId.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useState, useRef, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useChat } from '@/hooks/useChat';
import { MessageList, MessageItem } from '@/components/chat/MessageList';
import { InputBox } from '@/components/chat/InputBox';
import { StepVisualizer } from '@/components/chat/StepVisualizer';
import { useChatStore } from '@/stores/chatStore';

export const Route = createFileRoute('/chat/$sessionId')({
  component: ChatPage,
});

function ChatPage() {
  const { sessionId } = Route.useParams();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  
  const { messages, addMessage } = useChatStore();
  const { sendMessage, cancel, isStreaming, currentMessage, steps, usage } = useChat({
    sessionId,
    onComplete: (message) => {
      addMessage({
        id: crypto.randomUUID(),
        role: 'assistant',
        content: message,
        created_at: new Date().toISOString(),
      });
    },
  });
  
  const sessionMessages = messages.filter((m) => m.session_id === sessionId);
  
  // 虚拟滚动（长对话性能优化）
  const virtualizer = useVirtualizer({
    count: sessionMessages.length,
    getScrollElement: () => scrollContainerRef.current,
    estimateSize: () => 80, // 预估消息高度
    overscan: 5, // 预渲染缓冲
  });
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [sessionMessages, currentMessage]);
  
  const handleSubmit = (message: string) => {
    // 添加用户消息
    addMessage({
      id: crypto.randomUUID(),
      session_id: sessionId,
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    });
    
    // 发送到后端
    sendMessage({ message });
  };
  
  return (
    <div className="flex flex-col h-full">
      {/* 消息列表 - 虚拟滚动 */}
      <div 
        ref={scrollContainerRef} 
        className="flex-1 overflow-y-auto p-4"
      >
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualizer.getVirtualItems().map((virtualItem) => (
            <div
              key={virtualItem.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualItem.start}px)`,
              }}
              data-index={virtualItem.index}
              ref={virtualizer.measureElement}
            >
              <MessageItem message={sessionMessages[virtualItem.index]} />
            </div>
          ))}
        </div>
        
        {/* 流式输出中的消息 */}
        {isStreaming && currentMessage && (
          <div className="flex flex-col gap-2">
            <MessageList
              messages={[{
                id: 'streaming',
                role: 'assistant',
                content: currentMessage,
                created_at: new Date().toISOString(),
              }]}
            />
            {usage && (
              <div className="text-xs text-gray-500">
                Tokens: {usage.prompt} + {usage.completion}
              </div>
            )}
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* 步骤可视化 */}
      <StepVisualizer steps={steps} />
      
      {/* 输入框 */}
      <InputBox
        onSubmit={handleSubmit}
        onCancel={cancel}
        isStreaming={isStreaming}
        disabled={!sessionId}
      />
    </div>
  );
}
```

### 6.2 审批中心

```tsx
// src/routes/approval/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Button, Tag, Modal, Input, message } from 'antd';
import { CheckCircle, XCircle } from 'lucide-react';
import api from '@/services/api';
import { usePermission, Permissions } from '@/hooks/usePermission';
import type { ApprovalTask, ApprovalStatus } from '@/types/approval';

export const Route = createFileRoute('/approval/')({
  component: ApprovalPage,
});

const statusColors: Record<ApprovalStatus, string> = {
  pending: 'gold',
  approved: 'green',
  rejected: 'red',
  expired: 'default',
  cancelled: 'default',
};

const statusLabels: Record<ApprovalStatus, string> = {
  pending: '待审批',
  approved: '已通过',
  rejected: '已拒绝',
  expired: '已过期',
  cancelled: '已取消',
};

function ApprovalPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  
  const [selectedApproval, setSelectedApproval] = useState<ApprovalTask | null>(null);
  const [comment, setComment] = useState('');
  
  // 获取审批列表
  const { data, isLoading } = useQuery({
    queryKey: ['approvals'],
    queryFn: () => api.get<{ items: ApprovalTask[] }>('/approvals').then((r) => r.data),
  });
  
  // 审批操作
  const approveMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) =>
      api.post(`/approvals/${id}/approve`, { comment }),
    onSuccess: () => {
      message.success('审批已通过');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setSelectedApproval(null);
    },
  });
  
  const rejectMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) =>
      api.post(`/approvals/${id}/reject`, { comment }),
    onSuccess: () => {
      message.success('审批已拒绝');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setSelectedApproval(null);
    },
  });
  
  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
    },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      render: (type: string) => {
        const labels: Record<string, string> = {
          tool_approval: '工具审批',
          sensitive_action: '敏感操作',
          high_value_transaction: '高价值交易',
        };
        return labels[type] || type;
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      render: (priority: string) => {
        const colors: Record<string, string> = {
          low: 'default',
          normal: 'blue',
          high: 'orange',
          urgent: 'red',
        };
        return <Tag color={colors[priority]}>{priority.toUpperCase()}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: ApprovalStatus) => (
        <Tag color={statusColors[status]}>{statusLabels[status]}</Tag>
      ),
    },
    {
      title: '请求人',
      dataIndex: 'requester_id',
      key: 'requester_id',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: ApprovalTask) => (
        <div className="flex gap-2">
          {record.status === 'pending' && hasPermission(Permissions.APPROVAL_APPROVE) && (
            <>
              <Button
                type="primary"
                size="small"
                icon={<CheckCircle className="w-4 h-4" />}
                onClick={() => setSelectedApproval(record)}
              >
                审批
              </Button>
            </>
          )}
          <Button size="small" onClick={() => setSelectedApproval(record)}>
            详情
          </Button>
        </div>
      ),
    },
  ];
  
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">审批中心</h1>
      
      <Table
        columns={columns}
        dataSource={data?.items}
        loading={isLoading}
        rowKey="id"
        pagination={{ pageSize: 20 }}
      />
      
      {/* 审批弹窗 */}
      <Modal
        title="审批操作"
        open={!!selectedApproval}
        onCancel={() => setSelectedApproval(null)}
        footer={
          <div className="flex gap-2 justify-end">
            <Button onClick={() => setSelectedApproval(null)}>取消</Button>
            {selectedApproval?.status === 'pending' && (
              <>
                <Button
                  danger
                  onClick={() => rejectMutation.mutate({
                    id: selectedApproval.id,
                    comment,
                  })}
                  loading={rejectMutation.isPending}
                >
                  拒绝
                </Button>
                <Button
                  type="primary"
                  onClick={() => approveMutation.mutate({
                    id: selectedApproval.id,
                    comment,
                  })}
                  loading={approveMutation.isPending}
                >
                  通过
                </Button>
              </>
            )}
          </div>
        }
      >
        {selectedApproval && (
          <div className="space-y-4">
            <div>
              <strong>标题：</strong>{selectedApproval.title}
            </div>
            <div>
              <strong>描述：</strong>{selectedApproval.description}
            </div>
            <div>
              <strong>请求内容：</strong>
              <pre className="bg-gray-100 p-2 rounded text-sm overflow-auto">
                {JSON.stringify(selectedApproval.request_context, null, 2)}
              </pre>
            </div>
            {selectedApproval.status === 'pending' && (
              <div>
                <strong>审批意见：</strong>
                <Input.TextArea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="请输入审批意见（可选）"
                  rows={3}
                />
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
```

### 6.3 工具管理

```tsx
// src/routes/tools/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Button, Tag, Switch, Modal, Form, Input, Select, message } from 'antd';
import api from '@/services/api';
import { usePermission, Permissions } from '@/hooks/usePermission';
import type { ToolDefinition, ToolStatus } from '@/types/tools';

export const Route = createFileRoute('/tools/')({
  component: ToolsPage,
});

const statusColors: Record<ToolStatus, string> = {
  draft: 'default',
  active: 'green',
  disabled: 'orange',
  deprecated: 'gold',
  sunset: 'red',
};

const riskColors: Record<string, string> = {
  low: 'green',
  medium: 'blue',
  high: 'orange',
  critical: 'red',
};

function ToolsPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  
  // 获取工具列表
  const { data, isLoading } = useQuery({
    queryKey: ['tools'],
    queryFn: () => api.get<{ items: ToolDefinition[] }>('/internal/tools').then((r) => r.data),
  });
  
  // 启用/禁用工具
  const toggleMutation = useMutation({
    mutationFn: ({ name, enabled }: { name: string; enabled: boolean }) =>
      api.post(`/internal/tools/${name}/${enabled ? 'enable' : 'disable'}`),
    onSuccess: () => {
      message.success('状态已更新');
      queryClient.invalidateQueries({ queryKey: ['tools'] });
    },
  });
  
  const columns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: ToolDefinition) => (
        <div>
          <div className="font-medium">{name}</div>
          <div className="text-xs text-gray-500">{record.description}</div>
        </div>
      ),
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
    },
    {
      title: '类型',
      dataIndex: 'category',
      key: 'category',
    },
    {
      title: '风险等级',
      dataIndex: 'risk_level',
      key: 'risk_level',
      render: (level: string) => (
        <Tag color={riskColors[level]}>{level.toUpperCase()}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: ToolStatus) => (
        <Tag color={statusColors[status]}>{status}</Tag>
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      render: (enabled: boolean, record: ToolDefinition) => (
        hasPermission(Permissions.TOOL_WRITE) ? (
          <Switch
            checked={enabled}
            onChange={(checked) => toggleMutation.mutate({
              name: record.name,
              enabled: checked,
            })}
            disabled={record.status === 'sunset'}
          />
        ) : (
          <Tag>{enabled ? '是' : '否'}</Tag>
        )
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: ToolDefinition) => (
        <div className="flex gap-2">
          <Button size="small" onClick={() => {/* 查看详情 */}}>
            详情
          </Button>
          {hasPermission(Permissions.TOOL_WRITE) && (
            <Button size="small" onClick={() => {/* 编辑 */}}>
              编辑
            </Button>
          )}
        </div>
      ),
    },
  ];
  
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">工具管理</h1>
        {hasPermission(Permissions.TOOL_WRITE) && (
          <Button type="primary">注册新工具</Button>
        )}
      </div>
      
      <Table
        columns={columns}
        dataSource={data?.items}
        loading={isLoading}
        rowKey="name"
        pagination={{ pageSize: 20 }}
      />
    </div>
  );
}
```

---

## 7. 监控面板

### 7.1 Dashboard 设计

```tsx
// src/routes/dashboard/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { Card, Row, Col, Statistic } from 'antd';
import { Line, Pie, Bar } from 'echarts-for-react';
import api from '@/services/api';

export const Route = createFileRoute('/dashboard/')({
  component: DashboardPage,
});

interface DashboardStats {
  total_sessions: number;
  total_runs: number;
  total_tokens: number;
  total_cost_usd: number;
  avg_latency_ms: number;
  success_rate: number;
  runs_by_day: { date: string; count: number }[];
  tokens_by_model: { model: string; tokens: number }[];
  cost_by_day: { date: string; cost: number }[];
}

function DashboardPage() {
  const [refreshInterval, setRefreshInterval] = useState(60000);
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardStats>('/dashboard/stats').then((r) => r.data),
    refetchInterval,
  });
  
  // WebSocket 实时告警
  useEffect(() => {
    const ws = new WebSocket(`${import.meta.env.VITE_WS_URL}/alerts`);
    ws.onmessage = (event) => {
      const alert = JSON.parse(event.data);
      if (alert.severity === 'critical') {
        notification.error({
          message: '系统告警',
          description: alert.message,
          duration: 0,
        });
      }
    };
    return () => ws.close();
  }, []);
  
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">监控面板</h1>
        <Select
          value={refreshInterval}
          onChange={setRefreshInterval}
          options={[
            { label: '10秒', value: 10000 },
            { label: '30秒', value: 30000 },
            { label: '1分钟', value: 60000 },
            { label: '5分钟', value: 300000 },
          ]}
          style={{ width: 100 }}
        />
      </div>
      
      {/* 核心指标 */}
      <Row gutter={16} className="mb-6">
        <Col span={6}>
          <Card>
            <Statistic
              title="总会话数"
              value={data?.total_sessions}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总运行次数"
              value={data?.total_runs}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Token 消耗"
              value={data?.total_tokens}
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总成本 (USD)"
              value={data?.total_cost_usd}
              precision={2}
              loading={isLoading}
            />
          </Card>
        </Col>
      </Row>
      
      {/* 指标卡片 - 阈值告警 */}
      <Row gutter={16} className="mb-6">
        <Col span={12}>
          <Card 
            title="平均延迟"
            className={data?.avg_latency_ms && data.avg_latency_ms > 1000 ? 'border-red-500' : ''}
          >
            <Statistic
              value={data?.avg_latency_ms}
              suffix="ms"
              loading={isLoading}
              valueStyle={{
                color: data?.avg_latency_ms && data.avg_latency_ms > 1000 ? 'red' : undefined,
              }}
            />
            {data?.avg_latency_ms && data.avg_latency_ms > 1000 && (
              <Tag color="red">超过阈值</Tag>
            )}
          </Card>
        </Col>
        <Col span={12}>
          <Card 
            title="成功率"
            className={data?.success_rate && data.success_rate < 95 ? 'border-orange-500' : ''}
          >
            <Statistic
              value={data?.success_rate}
              suffix="%"
              precision={1}
              loading={isLoading}
              valueStyle={{
                color: data?.success_rate && data.success_rate < 95 ? 'orange' : undefined,
              }}
            />
            {data?.success_rate && data.success_rate < 95 && (
              <Tag color="orange">低于目标</Tag>
            )}
          </Card>
        </Col>
      </Row>
      
      {/* 图表 */}
      <Row gutter={16}>
        <Col span={12}>
          <Card title="每日运行次数">
            <Line
              data={{
                xAxis: { type: 'category', data: data?.runs_by_day.map((d) => d.date) },
                yAxis: { type: 'value' },
                series: [{ type: 'line', data: data?.runs_by_day.map((d) => d.count) }],
              }}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Token 按模型分布">
            <Pie
              data={{
                series: [{
                  type: 'pie',
                  data: data?.tokens_by_model.map((d) => ({ name: d.model, value: d.tokens })),
                }],
              }}
            />
          </Card>
        </Col>
      </Row>
      
      <Row gutter={16} className="mt-6">
        <Col span={24}>
          <Card title="每日成本趋势">
            <Bar
              data={{
                xAxis: { type: 'category', data: data?.cost_by_day.map((d) => d.date) },
                yAxis: { type: 'value' },
                series: [{ type: 'bar', data: data?.cost_by_day.map((d) => d.cost) }],
              }}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
```

### 7.2 图表数据聚合策略

> **性能优化**：大数据量时前端采样或后端聚合，避免渲染过多数据点。

```typescript
// src/utils/chartAggregation.ts

/** 时间序列数据聚合 */
export function aggregateTimeSeries(
  data: { date: string; value: number }[],
  maxPoints: number = 50
): { date: string; value: number }[] {
  if (data.length <= maxPoints) return data;
  
  const bucketSize = Math.ceil(data.length / maxPoints);
  const aggregated: { date: string; value: number }[] = [];
  
  for (let i = 0; i < data.length; i += bucketSize) {
    const bucket = data.slice(i, i + bucketSize);
    const sum = bucket.reduce((acc, item) => acc + item.value, 0);
    aggregated.push({
      date: bucket[0].date, // 使用桶的第一个日期
      value: sum,
    });
  }
  
  return aggregated;
}

/** 分桶聚合（保留峰值） */
export function aggregateWithPeak(
  data: { date: string; value: number }[],
  maxPoints: number = 50
): { date: string; value: number; peak?: number }[] {
  if (data.length <= maxPoints) return data;
  
  const bucketSize = Math.ceil(data.length / maxPoints);
  const aggregated: { date: string; value: number; peak?: number }[] = [];
  
  for (let i = 0; i < data.length; i += bucketSize) {
    const bucket = data.slice(i, i + bucketSize);
    const values = bucket.map((d) => d.value);
    aggregated.push({
      date: bucket[0].date,
      value: values.reduce((a, b) => a + b, 0),
      peak: Math.max(...values),
    });
  }
  
  return aggregated;
}

// 使用示例
const processedRunsByDay = aggregateTimeSeries(data?.runs_by_day || [], 30);
const processedCostByDay = aggregateWithPeak(data?.cost_by_day || [], 30);
```

```tsx
// 图表组件懒加载 + 数据聚合
import { lazy, Suspense } from 'react';

const LazyLine = lazy(() => 
  import('echarts-for-react').then((m) => ({ default: m.Line }))
);

function LazyLineChart({ data, title }: { data: any; title: string }) {
  const processedData = useMemo(() => 
    aggregateTimeSeries(data, 30), 
    [data]
  );
  
  return (
    <Suspense fallback={<Spin />}>
      <LazyLine
        data={{
          xAxis: { type: 'category', data: processedData.map((d) => d.date) },
          yAxis: { type: 'value' },
          series: [{ type: 'line', data: processedData.map((d) => d.value) }],
        }}
      />
    </Suspense>
  );
}
```

---

### 7.3 文件上传处理

```typescript
// src/components/ui/FileUpload.tsx

import { useState, useRef, useCallback } from 'react';
import { Upload, message, Progress, Button } from 'antd';
import { Upload as UploadIcon, X, FileText, Image, File } from 'lucide-react';
import type { UploadFile, UploadProps } from 'antd';

export interface FileUploadProps {
  accept?: string;
  maxSize?: number; // MB
  maxCount?: number;
  multiple?: boolean;
  value?: UploadFile[];
  onChange?: (files: UploadFile[]) => void;
  onUpload?: (files: File[]) => Promise<string[]>; // 返回文件 URL
  uploadUrl?: string;
}

export function FileUpload({
  accept,
  maxSize = 10,
  maxCount = 5,
  multiple = false,
  value = [],
  onChange,
  onUpload,
  uploadUrl = '/api/v1/upload',
}: FileUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  
  const beforeUpload = useCallback((file: File) => {
    // 文件大小检查
    const isLtMaxSize = file.size / 1024 / 1024 < maxSize;
    if (!isLtMaxSize) {
      message.error(`文件大小不能超过 ${maxSize}MB`);
      return Upload.LIST_IGNORE;
    }
    
    // 文件类型检查
    if (accept) {
      const acceptedTypes = accept.split(',').map((t) => t.trim());
      const fileExtension = `.${file.name.split('.').pop()}`;
      const mimeType = file.type;
      
      const isAccepted = acceptedTypes.some((type) => {
        if (type.startsWith('.')) {
          return fileExtension.toLowerCase() === type.toLowerCase();
        }
        if (type.endsWith('/*')) {
          return mimeType.startsWith(type.replace('/*', ''));
        }
        return mimeType === type;
      });
      
      if (!isAccepted) {
        message.error(`不支持的文件类型: ${file.name}`);
        return Upload.LIST_IGNORE;
      }
    }
    
    return true;
  }, [accept, maxSize]);
  
  const customRequest: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError, onProgress } = options;
    
    setUploading(true);
    setProgress(0);
    
    try {
      const formData = new FormData();
      formData.append('file', file as File);
      
      const response = await fetch(uploadUrl, {
        method: 'POST',
        body: formData,
        headers: {
          Authorization: `Bearer ${localStorage.getItem('accessToken')}`,
        },
      });
      
      if (!response.ok) {
        throw new Error(`Upload failed: ${response.status}`);
      }
      
      const result = await response.json();
      
      onProgress?.({ percent: 100 });
      onSuccess?.(result);
      
      message.success('上传成功');
    } catch (error) {
      onError?.(error as Error);
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };
  
  const handleRemove = (file: UploadFile) => {
    const newFiles = value.filter((f) => f.uid !== file.uid);
    onChange?.(newFiles);
  };
  
  const getFileIcon = (file: UploadFile) => {
    const type = file.type || '';
    if (type.startsWith('image/')) return <Image className="w-8 h-8" />;
    if (type.includes('pdf') || type.includes('document')) return <FileText className="w-8 h-8" />;
    return <File className="w-8 h-8" />;
  };
  
  return (
    <div className="file-upload">
      <Upload.Dragger
        accept={accept}
        multiple={multiple}
        maxCount={maxCount}
        fileList={value}
        beforeUpload={beforeUpload}
        customRequest={customRequest}
        onChange={({ fileList }) => onChange?.(fileList)}
        onRemove={handleRemove}
        itemRender={(originNode, file) => (
          <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg mb-2">
            {getFileIcon(file)}
            <div className="flex-1 min-w-0">
              <div className="font-medium truncate">{file.name}</div>
              <div className="text-xs text-gray-500">
                {(file.size! / 1024).toFixed(1)} KB
              </div>
              {file.status === 'uploading' && (
                <Progress percent={file.percent as number} size="small" />
              )}
            </div>
            <Button
              type="text"
              icon={<X className="w-4 h-4" />}
              onClick={() => handleRemove(file)}
            />
          </div>
        )}
      >
        <p className="ant-upload-drag-icon">
          <UploadIcon className="w-12 h-12 text-gray-400" />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持单个或批量上传，最大 {maxSize}MB
        </p>
      </Upload.Dragger>
    </div>
  );
}

// 使用示例：知识库文档上传
<DocumentUploader
  accept=".pdf,.doc,.docx,.txt,.md"
  maxSize={50}
  maxCount={10}
  multiple
  onUpload={async (files) => {
    // 上传到知识库
    const urls = await uploadToKnowledgeBase(files);
    return urls;
  }}
/>
```

#### 7.4 会话管理页面

```tsx
// src/routes/chat/index.tsx

import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { List, Button, Tag, Input, Dropdown, Empty, Spin, Popconfirm } from 'antd';
import { 
  MessageSquare, Plus, Search, MoreHorizontal, 
  Archive, Trash2, Edit2, Clock 
} from 'lucide-react';
import api from '@/services/api';
import type { Session } from '@/types/chat';

export const Route = createFileRoute('/chat/')({
  component: SessionsPage,
});

function SessionsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchQuery, setSearchQuery] = useState('');
  
  // 获取会话列表
  const { data, isLoading } = useQuery({
    queryKey: ['sessions', searchQuery],
    queryFn: () => api.get<{ items: Session[] }>('/sessions', {
      params: { search: searchQuery },
    }).then((r) => r.data),
  });
  
  // 创建新会话
  const createMutation = useMutation({
    mutationFn: () => api.post('/sessions', { session_type: 'chat' }),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      navigate({ to: `/chat/${response.data.id}` });
    },
  });
  
  // 归档会话
  const archiveMutation = useMutation({
    mutationFn: (id: string) => api.post(`/sessions/${id}/archive`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });
  
  // 删除会话
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/sessions/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });
  
  // 更新会话标题
  const updateMutation = useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      api.patch(`/sessions/${id}`, { title }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });
  
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState('');
  
  const handleEdit = (session: Session) => {
    setEditingId(session.id);
    setEditingTitle(session.title || '');
  };
  
  const handleSaveEdit = () => {
    if (editingId && editingTitle.trim()) {
      updateMutation.mutate({ id: editingId, title: editingTitle.trim() });
    }
    setEditingId(null);
  };
  
  const statusColors: Record<string, string> = {
    active: 'green',
    archived: 'orange',
    closed: 'default',
  };
  
  const statusLabels: Record<string, string> = {
    active: '活跃',
    archived: '已归档',
    closed: '已关闭',
  };
  
  return (
    <div className="p-6 h-full flex flex-col">
      {/* 标题栏 */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">会话列表</h1>
        <Button
          type="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={() => createMutation.mutate()}
          loading={createMutation.isPending}
        >
          新建会话
        </Button>
      </div>
      
      {/* 搜索栏 */}
      <div className="mb-4">
        <Input
          prefix={<Search className="w-4 h-4 text-gray-400" />}
          placeholder="搜索会话..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
        />
      </div>
      
      {/* 会话列表 */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex justify-center py-12">
            <Spin />
          </div>
        ) : !data?.items?.length ? (
          <Empty description="暂无会话" />
        ) : (
          <List
            dataSource={data.items}
            renderItem={(session) => (
              <List.Item
                className="cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg px-4"
                onClick={() => {
                  if (!editingId) {
                    navigate({ to: `/chat/${session.id}` });
                  }
                }}
              >
                <div className="flex items-center gap-3 w-full">
                  <MessageSquare className="w-5 h-5 text-gray-400 flex-shrink-0" />
                  
                  <div className="flex-1 min-w-0">
                    {editingId === session.id ? (
                      <Input
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onBlur={handleSaveEdit}
                        onPressEnter={handleSaveEdit}
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <div className="font-medium truncate">
                        {session.title || '新会话'}
                      </div>
                    )}
                    <div className="text-xs text-gray-500 flex items-center gap-2">
                      <Clock className="w-3 h-3" />
                      {new Date(session.updated_at).toLocaleString()}
                    </div>
                  </div>
                  
                  <Tag color={statusColors[session.status]}>
                    {statusLabels[session.status]}
                  </Tag>
                  
                  <Dropdown
                    menu={{
                      items: [
                        {
                          key: 'edit',
                          label: '重命名',
                          icon: <Edit2 className="w-4 h-4" />,
                          onClick: (e) => {
                            e.domEvent.stopPropagation();
                            handleEdit(session);
                          },
                        },
                        {
                          key: 'archive',
                          label: session.status === 'archived' ? '取消归档' : '归档',
                          icon: <Archive className="w-4 h-4" />,
                          onClick: (e) => {
                            e.domEvent.stopPropagation();
                            archiveMutation.mutate(session.id);
                          },
                        },
                        {
                          type: 'divider',
                        },
                        {
                          key: 'delete',
                          label: '删除',
                          icon: <Trash2 className="w-4 h-4" />,
                          danger: true,
                          onClick: (e) => {
                            e.domEvent.stopPropagation();
                          },
                        },
                      ],
                      onClick: (info) => {
                        if (info.key === 'delete') {
                          deleteMutation.mutate(session.id);
                        }
                      },
                    }}
                    trigger={['click']}
                  >
                    <Button
                      type="text"
                      icon={<MoreHorizontal className="w-4 h-4" />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Dropdown>
                </div>
              </List.Item>
            )}
          />
        )}
      </div>
    </div>
  );
}
```

---

## 8. 错误处理

### 8.1 全局错误边界

> **观测要求**：前端日志、性能指标、错误上报与后端观测体系打通。

```tsx
// src/components/feedback/ErrorBoundary.tsx

import { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from 'antd';
import { AlertTriangle } from 'lucide-react';
import * as Sentry from '@sentry/react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  eventId?: string; // Sentry 事件 ID
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  
  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Sentry 上报（自动携带面包屑、用户信息）
    const eventId = Sentry.captureException(error, {
      contexts: {
        react: {
          componentStack: errorInfo.componentStack,
        },
      },
      tags: {
        route: window.location.pathname,
      },
    });
    
    this.setState({ eventId });
    
    // 本地日志（开发调试）
    console.error('ErrorBoundary caught:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      
      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8">
          <AlertTriangle className="w-16 h-16 text-red-500 mb-4" />
          <h2 className="text-xl font-bold mb-2">出现错误</h2>
          <p className="text-gray-500 mb-2">
            {this.state.error?.message || '未知错误'}
          </p>
          {/* 显示追踪 ID，方便用户反馈 */}
          <p className="text-xs text-gray-400 mb-4">
            错误追踪 ID: {this.state.eventId || 'N/A'}
          </p>
          <div className="flex gap-2">
            <Button onClick={() => Sentry.showReportDialog({ eventId: this.state.eventId })}>
              反馈问题
            </Button>
            <Button type="primary" onClick={() => window.location.reload()}>
              刷新页面
            </Button>
          </div>
        </div>
      );
    }
    
    return this.props.children;
  }
}
```

```typescript
// src/main.tsx - Sentry 初始化
import * as Sentry from '@sentry/react';

if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.VITE_ENV,
    release: import.meta.env.VITE_APP_VERSION,
    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({ maskAllText: false }),
    ],
    tracesSampleRate: 0.1, // 10% 采样
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0, // 错误时 100% 录屏
    beforeSend(event) {
      // 脱敏敏感信息
      if (event.request?.headers) {
        delete event.request.headers['Authorization'];
      }
      return event;
    },
  });
}
```

### 8.2 API 错误统一处理

```typescript
// src/utils/error.ts

import { notification } from 'antd';
import { ErrorCode } from '@/types/error';
import { useAuthStore } from '@/stores/authStore';

/** 错误码到用户消息的映射 */
export const ErrorMessageMap: Partial<Record<ErrorCode, string>> = {
  // 通用
  [ErrorCode.ERR_INVALID_REQUEST]: '请求参数无效，请检查输入',
  [ErrorCode.ERR_UNAUTHORIZED]: '登录已过期，请重新登录',
  [ErrorCode.ERR_FORBIDDEN]: '您没有权限执行此操作',
  [ErrorCode.ERR_RATE_LIMITED]: '请求过于频繁，请稍后再试',
  [ErrorCode.ERR_TIMEOUT]: '请求超时，请稍后再试',
  [ErrorCode.ERR_SERVICE_UNAVAILABLE]: '服务暂不可用，请稍后再试',
  
  // Agent
  [ErrorCode.ERR_AGENT_MAX_STEPS_EXCEEDED]: '任务执行步骤过多，已自动终止',
  [ErrorCode.ERR_AGENT_CONTEXT_TOO_LONG]: '对话内容过长，请开启新会话',
  [ErrorCode.ERR_AGENT_TOOL_NOT_FOUND]: '请求的工具不存在',
  
  // 模型
  [ErrorCode.ERR_MODEL_ALL_PROVIDERS_DOWN]: 'AI 服务暂时不可用，请稍后再试',
  [ErrorCode.ERR_MODEL_TOKEN_LIMIT]: '内容超出长度限制',
  [ErrorCode.ERR_MODEL_CONTENT_FILTERED]: '内容包含敏感信息，已被过滤',
  [ErrorCode.ERR_MODEL_QUOTA_EXCEEDED]: '使用额度已用尽，请联系管理员',
  
  // 工具
  [ErrorCode.ERR_TOOL_VALIDATION_FAILED]: '工具参数校验失败',
  [ErrorCode.ERR_TOOL_EXECUTION_FAILED]: '工具执行失败',
  [ErrorCode.ERR_TOOL_RISK_REJECTED]: '操作被风控拦截',
  [ErrorCode.ERR_TOOL_APPROVAL_REQUIRED]: '此操作需要审批',
};

/** 获取用户友好的错误消息 */
export function getUserMessage(error: { code: ErrorCode; user_message?: string }): string {
  if (error.user_message) return error.user_message;
  return ErrorMessageMap[error.code] || '操作失败，请稍后再试';
}

/** API 错误统一处理 */
export function handleApiError(error: unknown, options?: { silent?: boolean }) {
  if (options?.silent) return;
  
  // Axios 错误
  if (axios.isAxiosError(error)) {
    const { response, code } = error;
    
    // 网络错误
    if (code === 'ERR_NETWORK' || !response) {
      notification.error({
        message: '网络错误',
        description: '无法连接服务器，请检查网络连接',
      });
      return;
    }
    
    const errorData = response.data?.error;
    
    // 业务错误
    if (errorData) {
      const userMsg = getUserMessage(errorData);
      
      // 401 自动登交由拦截器处理
      if (response.status === 401) return;
      
      notification.error({
        message: '操作失败',
        description: userMsg,
        duration: errorData.code === ErrorCode.ERR_RATE_LIMITED ? 10 : 4.5,
      });
      return;
    }
    
    // HTTP 状态码错误
    notification.error({
      message: '请求失败',
      description: `HTTP ${response.status}: ${response.statusText}`,
    });
    return;
  }
  
  // 其他错误
  notification.error({
    message: '未知错误',
    description: error instanceof Error ? error.message : '请刷新页面重试',
  });
}
```

### 8.3 网络状态检测

```typescript
// src/hooks/useNetworkStatus.ts

import { useState, useEffect, useCallback } from 'react';
import { notification } from 'antd';

export interface NetworkStatus {
  isOnline: boolean;
  isSlowConnection: boolean;
  effectiveType: string;
  downlink: number;
}

export function useNetworkStatus() {
  const [status, setStatus] = useState<NetworkStatus>({
    isOnline: navigator.onLine,
    isSlowConnection: false,
    effectiveType: '4g',
    downlink: 10,
  });
  
  useEffect(() => {
    const handleOnline = () => {
      setStatus((s) => ({ ...s, isOnline: true }));
      notification.success({ message: '网络已恢复', duration: 2 });
    };
    
    const handleOffline = () => {
      setStatus((s) => ({ ...s, isOnline: false }));
      notification.warning({ message: '网络已断开', description: '请检查网络连接', duration: 0 });
    };
    
    // Network Information API（部分浏览器支持）
    const connection = (navigator as any).connection;
    if (connection) {
      const handleConnectionChange = () => {
        setStatus((s) => ({
          ...s,
          isSlowConnection: connection.effectiveType === '2g' || connection.effectiveType === 'slow-2g',
          effectiveType: connection.effectiveType,
          downlink: connection.downlink,
        }));
      };
      connection.addEventListener('change', handleConnectionChange);
      handleConnectionChange();
      
      return () => {
        connection.removeEventListener('change', handleConnectionChange);
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      };
    }
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);
  
  return status;
}
```

### 8.4 连接状态 UI 提示

```tsx
// src/components/feedback/ConnectionStatus.tsx

import { Badge, Tooltip } from 'antd';
import { Wifi, WifiOff, Loader2 } from 'lucide-react';
import { useNetworkStatus } from '@/hooks/useNetworkStatus';

interface Props {
  isStreaming?: boolean;
  isConnected?: boolean;
}

export function ConnectionStatus({ isStreaming, isConnected }: Props) {
  const { isOnline, isSlowConnection, effectiveType } = useNetworkStatus();
  
  if (!isOnline) {
    return (
      <Tooltip title="网络已断开">
        <Badge status="error" />
        <WifiOff className="w-4 h-4 text-red-500" />
      </Tooltip>
    );
  }
  
  if (isStreaming) {
    return (
      <Tooltip title="正在接收响应...">
        <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />
      </Tooltip>
    );
  }
  
  if (isConnected === false) {
    return (
      <Tooltip title="连接已断开，正在重连...">
        <Badge status="warning" />
        <Wifi className="w-4 h-4 text-orange-500" />
      </Tooltip>
    );
  }
  
  if (isSlowConnection) {
    return (
      <Tooltip title={`网络较慢 (${effectiveType})`}>
        <Badge status="warning" />
        <Wifi className="w-4 h-4 text-orange-500" />
      </Tooltip>
    );
  }
  
  return null;
}
```

---

### 8.5 知识库管理页面

```tsx
// src/routes/knowledge/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Row, Col, Button, Input, Tag, Table, Modal, Form, Select, Progress, message } from 'antd';
import { Plus, Search, FileText, Trash2, Eye, Upload } from 'lucide-react';
import api from '@/services/api';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { FileUpload } from '@/components/ui/FileUpload';

export const Route = createFileRoute('/knowledge/')({
  component: KnowledgePage,
});

interface KnowledgeDocument {
  id: string;
  tenant_id: string;
  title: string;
  content_type: string;
  file_size: number;
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  chunk_count: number;
  indexed_at?: string;
  created_at: string;
  error_message?: string;
}

const statusConfig: Record<string, { color: string; label: string }> = {
  pending: { color: 'default', label: '待处理' },
  indexing: { color: 'processing', label: '索引中' },
  ready: { color: 'success', label: '就绪' },
  failed: { color: 'error', label: '失败' },
};

function KnowledgePage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  const [searchQuery, setSearchQuery] = useState('');
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<UploadFile[]>([]);
  
  // 获取文档列表
  const { data, isLoading } = useQuery({
    queryKey: ['knowledge', searchQuery],
    queryFn: () => api.get<{ items: KnowledgeDocument[] }>('/knowledge/documents', {
      params: { search: searchQuery },
    }).then((r) => r.data),
  });
  
  // 上传文档
  const uploadMutation = useMutation({
    mutationFn: async (files: File[]) => {
      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));
      const response = await api.post('/knowledge/documents', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return response.data;
    },
    onSuccess: () => {
      message.success('文档上传成功，正在索引中');
      setUploadModalOpen(false);
      setSelectedFiles([]);
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
    onError: () => {
      message.error('上传失败');
    },
  });
  
  // 删除文档
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/knowledge/documents/${id}`),
    onSuccess: () => {
      message.success('文档已删除');
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
  });
  
  // 重新索引
  const reindexMutation = useMutation({
    mutationFn: (id: string) => api.post(`/knowledge/documents/${id}/reindex`),
    onSuccess: () => {
      message.success('已开始重新索引');
      queryClient.invalidateQueries({ queryKey: ['knowledge'] });
    },
  });
  
  const columns = [
    {
      title: '文档名称',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record: KnowledgeDocument) => (
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-gray-400" />
          <span>{title}</span>
        </div>
      ),
    },
    {
      title: '类型',
      dataIndex: 'content_type',
      key: 'content_type',
      width: 120,
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size: number) => `${(size / 1024).toFixed(1)} KB`,
    },
    {
      title: '分块数',
      dataIndex: 'chunk_count',
      key: 'chunk_count',
      width: 100,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string, record: KnowledgeDocument) => {
        const config = statusConfig[status];
        if (status === 'indexing') {
          return (
            <div className="flex items-center gap-2">
              <Progress type="circle" percent={50} size={16} />
              <span className="text-blue-500">{config.label}</span>
            </div>
          );
        }
        if (status === 'failed' && record.error_message) {
          return (
            <Tooltip title={record.error_message}>
              <Tag color={config.color}>{config.label}</Tag>
            </Tooltip>
          );
        }
        return <Tag color={config.color}>{config.label}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (t: string) => new Date(t).toLocaleString(),
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_: unknown, record: KnowledgeDocument) => (
        <div className="flex gap-2">
          <Button size="small" icon={<Eye className="w-4 h-4" />}>
            查看
          </Button>
          {record.status === 'failed' && (
            <Button size="small" onClick={() => reindexMutation.mutate(record.id)}>
              重试
            </Button>
          )}
          {hasPermission(Permissions.TOOL_DELETE) && (
            <Popconfirm title="确定删除此文档？" onConfirm={() => deleteMutation.mutate(record.id)}>
              <Button size="small" danger icon={<Trash2 className="w-4 h-4" />} />
            </Popconfirm>
          )}
        </div>
      ),
    },
  ];
  
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">知识库管理</h1>
        <Button
          type="primary"
          icon={<Upload className="w-4 h-4" />}
          onClick={() => setUploadModalOpen(true)}
        >
          上传文档
        </Button>
      </div>
      
      {/* 搜索 */}
      <div className="mb-4 max-w-md">
        <Input
          prefix={<Search className="w-4 h-4 text-gray-400" />}
          placeholder="搜索文档..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
        />
      </div>
      
      {/* 统计卡片 */}
      <Row gutter={16} className="mb-6">
        <Col span={6}>
          <Card>
            <Statistic title="总文档数" value={data?.items?.length || 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="就绪文档"
              value={data?.items?.filter((d) => d.status === 'ready').length || 0}
              valueStyle={{ color: 'green' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="索引中"
              value={data?.items?.filter((d) => d.status === 'indexing').length || 0}
              valueStyle={{ color: 'blue' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="失败"
              value={data?.items?.filter((d) => d.status === 'failed').length || 0}
              valueStyle={{ color: 'red' }}
            />
          </Card>
        </Col>
      </Row>
      
      {/* 文档列表 */}
      <Table
        columns={columns}
        dataSource={data?.items}
        loading={isLoading}
        rowKey="id"
        pagination={{ pageSize: 20 }}
      />
      
      {/* 上传弹窗 */}
      <Modal
        title="上传文档"
        open={uploadModalOpen}
        onCancel={() => {
          setUploadModalOpen(false);
          setSelectedFiles([]);
        }}
        onOk={() => {
          const files = selectedFiles.map((f) => f.originFileObj as File);
          uploadMutation.mutate(files);
        }}
        confirmLoading={uploadMutation.isPending}
      >
        <FileUpload
          accept=".pdf,.doc,.docx,.txt,.md,.json"
          maxSize={50}
          maxCount={10}
          multiple
          value={selectedFiles}
          onChange={setSelectedFiles}
        />
      </Modal>
    </div>
  );
}
```

---

### 8.6 租户配置页面

```tsx
// src/routes/tenant/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Form, Input, Select, Switch, Button, Divider, message, Spin, Alert } from 'antd';
import { Save, RefreshCw } from 'lucide-react';
import api from '@/services/api';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { useAuthStore } from '@/stores/authStore';

export const Route = createFileRoute('/tenant/')({
  component: TenantConfigPage,
});

interface TenantConfig {
  id: string;
  name: string;
  tier: 'free' | 'standard' | 'premium' | 'enterprise';
  features: string[];
  settings: {
    max_sessions_per_user: number;
    max_tokens_per_day: number;
    max_concurrent_runs: number;
    allowed_models: string[];
    default_model: string;
    enable_knowledge_base: boolean;
    enable_multi_agent: boolean;
    data_retention_days: number;
  };
  quotas: {
    daily_tokens: number;
    monthly_cost_usd: number;
  };
  created_at: string;
  updated_at: string;
}

function TenantConfigPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  const { tenant } = useAuthStore();
  const [form] = Form.useForm();
  
  const canEdit = hasPermission(Permissions.TENANT_WRITE);
  
  // 获取租户配置
  const { data, isLoading } = useQuery({
    queryKey: ['tenant', tenant?.id],
    queryFn: () => api.get<TenantConfig>(`/tenants/${tenant?.id}`).then((r) => r.data),
    enabled: !!tenant?.id,
  });
  
  // 更新配置
  const updateMutation = useMutation({
    mutationFn: (values: Partial<TenantConfig['settings']>) =>
      api.patch(`/tenants/${tenant?.id}/settings`, values),
    onSuccess: () => {
      message.success('配置已保存');
      queryClient.invalidateQueries({ queryKey: ['tenant'] });
    },
    onError: () => {
      message.error('保存失败');
    },
  });
  
  // 重置为默认配置
  const resetMutation = useMutation({
    mutationFn: () => api.post(`/tenants/${tenant?.id}/settings/reset`),
    onSuccess: () => {
      message.success('已重置为默认配置');
      queryClient.invalidateQueries({ queryKey: ['tenant'] });
    },
  });
  
  useEffect(() => {
    if (data) {
      form.setFieldsValue(data.settings);
    }
  }, [data, form]);
  
  if (isLoading) {
    return <Spin className="flex justify-center py-12" />;
  }
  
  if (!canEdit) {
    return (
      <div className="p-6">
        <Alert
          type="warning"
          message="您没有修改租户配置的权限"
          description="请联系管理员获取权限"
          showIcon
        />
      </div>
    );
  }
  
  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">租户配置</h1>
          <p className="text-gray-500">{tenant?.name} ({tenant?.tier})</p>
        </div>
        <Button
          icon={<RefreshCw className="w-4 h-4" />}
          onClick={() => resetMutation.mutate()}
          loading={resetMutation.isPending}
        >
          重置默认
        </Button>
      </div>
      
      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => updateMutation.mutate(values)}
      >
        {/* 基础设置 */}
        <Card title="基础设置" className="mb-4">
          <div className="grid grid-cols-2 gap-4">
            <Form.Item
              name="max_sessions_per_user"
              label="每用户最大会话数"
              rules={[{ required: true }]}
            >
              <Input type="number" min={1} max={1000} />
            </Form.Item>
            
            <Form.Item
              name="max_tokens_per_day"
              label="每日 Token 限额"
              rules={[{ required: true }]}
            >
              <Input type="number" min={1000} />
            </Form.Item>
            
            <Form.Item
              name="max_concurrent_runs"
              label="最大并发运行数"
              rules={[{ required: true }]}
            >
              <Input type="number" min={1} max={100} />
            </Form.Item>
            
            <Form.Item
              name="data_retention_days"
              label="数据保留天数"
              rules={[{ required: true }]}
            >
              <Input type="number" min={7} max={365} />
            </Form.Item>
          </div>
        </Card>
        
        {/* 模型设置 */}
        <Card title="模型设置" className="mb-4">
          <Form.Item
            name="default_model"
            label="默认模型"
            rules={[{ required: true }]}
          >
            <Select
              options={[
                { label: 'DeepSeek V3', value: 'deepseek-v3' },
                { label: 'DeepSeek R1', value: 'deepseek-r1' },
                { label: 'Qwen Max', value: 'qwen-max' },
                { label: 'GLM-4', value: 'glm-4' },
              ]}
            />
          </Form.Item>
          
          <Form.Item
            name="allowed_models"
            label="允许使用的模型"
            rules={[{ required: true }]}
          >
            <Select
              mode="multiple"
              options={[
                { label: 'DeepSeek V3', value: 'deepseek-v3' },
                { label: 'DeepSeek R1', value: 'deepseek-r1' },
                { label: 'Qwen Max', value: 'qwen-max' },
                { label: 'GLM-4', value: 'glm-4' },
              ]}
            />
          </Form.Item>
        </Card>
        
        {/* 功能开关 */}
        <Card title="功能开关" className="mb-4">
          <div className="grid grid-cols-2 gap-4">
            <Form.Item
              name="enable_knowledge_base"
              label="启用知识库"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
            
            <Form.Item
              name="enable_multi_agent"
              label="启用多 Agent 协作"
              valuePropName="checked"
            >
              <Switch />
            </Form.Item>
          </div>
        </Card>
        
        {/* 配额信息（只读） */}
        <Card title="当前配额">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-gray-500">今日已用 Token</span>
              <div className="text-2xl font-bold">
                {data?.quotas.daily_tokens?.toLocaleString() || 0}
              </div>
            </div>
            <div>
              <span className="text-gray-500">本月已用成本</span>
              <div className="text-2xl font-bold">
                ${data?.quotas.monthly_cost_usd?.toFixed(2) || '0.00'}
              </div>
            </div>
          </div>
        </Card>
        
        <Divider />
        
        <div className="flex justify-end gap-2">
          <Button onClick={() => form.resetFields()}>取消</Button>
          <Button
            type="primary"
            htmlType="submit"
            icon={<Save className="w-4 h-4" />}
            loading={updateMutation.isPending}
          >
            保存配置
          </Button>
        </div>
      </Form>
    </div>
  );
}
```

---

### 8.7 用户与角色管理

```tsx
// src/routes/users/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Table, Button, Tag, Modal, Form, Input, Select, Switch, message, Popconfirm } from 'antd';
import { Plus, Edit2, Trash2, UserCog } from 'lucide-react';
import api from '@/services/api';
import { usePermission, Permissions } from '@/hooks/usePermission';

export const Route = createFileRoute('/users/')({
  component: UsersPage,
});

interface User {
  id: string;
  username: string;
  email: string;
  roles: string[];
  status: 'active' | 'inactive' | 'suspended';
  last_login_at?: string;
  created_at: string;
}

const statusColors: Record<string, string> = {
  active: 'green',
  inactive: 'default',
  suspended: 'red',
};

function UsersPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form] = Form.useForm();
  
  const canEdit = hasPermission(Permissions.TENANT_WRITE);
  
  // 获取用户列表
  const { data, isLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.get<{ items: User[] }>('/users').then((r) => r.data),
  });
  
  // 创建用户
  const createMutation = useMutation({
    mutationFn: (values: Partial<User>) => api.post('/users', values),
    onSuccess: () => {
      message.success('用户创建成功');
      setModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
  
  // 更新用户
  const updateMutation = useMutation({
    mutationFn: ({ id, ...values }: Partial<User> & { id: string }) =>
      api.patch(`/users/${id}`, values),
    onSuccess: () => {
      message.success('用户更新成功');
      setModalOpen(false);
      setEditingUser(null);
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
  
  // 删除用户
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => {
      message.success('用户已删除');
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });
  
  const handleEdit = (user: User) => {
    setEditingUser(user);
    form.setFieldsValue(user);
    setModalOpen(true);
  };
  
  const handleSubmit = (values: Partial<User>) => {
    if (editingUser) {
      updateMutation.mutate({ id: editingUser.id, ...values });
    } else {
      createMutation.mutate(values);
    }
  };
  
  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '角色',
      dataIndex: 'roles',
      key: 'roles',
      render: (roles: string[]) => (
        <div className="flex gap-1">
          {roles.map((role) => (
            <Tag key={role} color={role === 'admin' ? 'red' : 'blue'}>
              {role}
            </Tag>
          ))}
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={statusColors[status]}>{status}</Tag>
      ),
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      render: (t?: string) => (t ? new Date(t).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: User) => (
        <div className="flex gap-2">
          <Button size="small" icon={<Edit2 className="w-4 h-4" />} onClick={() => handleEdit(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此用户？" onConfirm={() => deleteMutation.mutate(record.id)}>
            <Button size="small" danger icon={<Trash2 className="w-4 h-4" />} />
          </Popconfirm>
        </div>
      ),
    },
  ];
  
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">用户管理</h1>
        <Button
          type="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={() => {
            setEditingUser(null);
            form.resetFields();
            setModalOpen(true);
          }}
          disabled={!canEdit}
        >
          添加用户
        </Button>
      </div>
      
      <Table columns={columns} dataSource={data?.items} loading={isLoading} rowKey="id" />
      
      <Modal
        title={editingUser ? '编辑用户' : '添加用户'}
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          setEditingUser(null);
        }}
        onOk={() => form.submit()}
        confirmLoading={createMutation.isPending || updateMutation.isPending}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input disabled={!!editingUser} />
          </Form.Item>
          <Form.Item name="email" label="邮箱" rules={[{ required: true, type: 'email' }]}>
            <Input />
          </Form.Item>
          {!editingUser && (
            <Form.Item name="password" label="密码" rules={[{ required: !editingUser }]}>
              <Input.Password />
            </Form.Item>
          )}
          <Form.Item name="roles" label="角色" rules={[{ required: true }]}>
            <Select
              mode="multiple"
              options={[
                { label: '管理员 (admin)', value: 'admin' },
                { label: '操作员 (operator)', value: 'operator' },
                { label: '查看者 (viewer)', value: 'viewer' },
              ]}
            />
          </Form.Item>
          <Form.Item name="status" label="状态" rules={[{ required: true }]}>
            <Select
              options={[
                { label: '活跃', value: 'active' },
                { label: '停用', value: 'inactive' },
                { label: '封禁', value: 'suspended' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
```

---

### 8.8 通知中心

```tsx
// src/routes/notifications/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { List, Button, Badge, Tabs, Empty, Spin, Tag, Popconfirm } from 'antd';
import { Bell, Check, Trash2, CheckCheck } from 'lucide-react';
import api from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';

export const Route = createFileRoute('/notifications/')({
  component: NotificationsPage,
});

interface Notification {
  id: string;
  type: 'approval' | 'system' | 'alert' | 'info';
  title: string;
  message: string;
  read: boolean;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  action_url?: string;
  created_at: string;
}

const typeColors: Record<string, string> = {
  approval: 'blue',
  system: 'green',
  alert: 'orange',
  info: 'default',
};

const priorityColors: Record<string, string> = {
  low: 'default',
  normal: 'blue',
  high: 'orange',
  urgent: 'red',
};

function NotificationsPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('all');
  
  // 获取通知列表
  const { data, isLoading } = useQuery({
    queryKey: ['notifications', activeTab],
    queryFn: () => api.get<{ items: Notification[]; unread_count: number }>('/notifications', {
      params: { filter: activeTab },
    }).then((r) => r.data),
  });
  
  // WebSocket 实时通知
  useWebSocket<{ type: string; notification: Notification }>({
    url: `${import.meta.env.VITE_WS_URL}/notifications`,
    onMessage: (data) => {
      if (data.type === 'notification') {
        queryClient.invalidateQueries({ queryKey: ['notifications'] });
      }
    },
  });
  
  // 标记已读
  const markReadMutation = useMutation({
    mutationFn: (id: string) => api.post(`/notifications/${id}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });
  
  // 全部标记已读
  const markAllReadMutation = useMutation({
    mutationFn: () => api.post('/notifications/read-all'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });
  
  // 删除通知
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/notifications/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });
  
  // 清空已读通知
  const clearReadMutation = useMutation({
    mutationFn: () => api.delete('/notifications/read'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });
  
  const handleNotificationClick = (notification: Notification) => {
    if (!notification.read) {
      markReadMutation.mutate(notification.id);
    }
    if (notification.action_url) {
      window.location.href = notification.action_url;
    }
  };
  
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold">通知中心</h1>
          {data?.unread_count ? (
            <Badge count={data.unread_count} />
          ) : null}
        </div>
        <div className="flex gap-2">
          <Button
            icon={<CheckCheck className="w-4 h-4" />}
            onClick={() => markAllReadMutation.mutate()}
            disabled={!data?.unread_count}
          >
            全部已读
          </Button>
          <Popconfirm title="确定清空所有已读通知？" onConfirm={() => clearReadMutation.mutate()}>
            <Button icon={<Trash2 className="w-4 h-4" />}>
              清空已读
            </Button>
          </Popconfirm>
        </div>
      </div>
      
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'all', label: '全部' },
          { key: 'unread', label: '未读' },
          { key: 'approval', label: '审批' },
          { key: 'system', label: '系统' },
        ]}
      />
      
      {isLoading ? (
        <Spin className="flex justify-center py-12" />
      ) : !data?.items?.length ? (
        <Empty description="暂无通知" />
      ) : (
        <List
          dataSource={data.items}
          renderItem={(item) => (
            <List.Item
              className={`
                cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800
                rounded-lg px-4 ${!item.read ? 'bg-blue-50 dark:bg-blue-900/20' : ''}
              `}
              onClick={() => handleNotificationClick(item)}
            >
              <div className="flex items-start gap-3 w-full">
                <div className="flex-shrink-0 mt-1">
                  {!item.read ? (
                    <div className="w-2 h-2 bg-blue-500 rounded-full" />
                  ) : (
                    <Bell className="w-4 h-4 text-gray-300" />
                  )}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`font-medium ${!item.read ? 'text-blue-600' : ''}`}>
                      {item.title}
                    </span>
                    <Tag color={typeColors[item.type]}>{item.type}</Tag>
                    {item.priority !== 'normal' && (
                      <Tag color={priorityColors[item.priority]}>{item.priority}</Tag>
                    )}
                  </div>
                  <p className="text-gray-600 dark:text-gray-400 text-sm mt-1">
                    {item.message}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(item.created_at).toLocaleString()}
                  </p>
                </div>
                
                <div className="flex gap-1">
                  {!item.read && (
                    <Button
                      type="text"
                      size="small"
                      icon={<Check className="w-4 h-4" />}
                      onClick={(e) => {
                        e.stopPropagation();
                        markReadMutation.mutate(item.id);
                      }}
                    />
                  )}
                  <Button
                    type="text"
                    size="small"
                    icon={<Trash2 className="w-4 h-4" />}
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteMutation.mutate(item.id);
                    }}
                  />
                </div>
              </div>
            </List.Item>
          )}
        />
      )}
    </div>
  );
}
```

---

### 8.9 快捷键系统

```tsx
// src/components/ui/KeyboardShortcuts.tsx

import { useEffect, useCallback } from 'react';
import { useHotkeys } from 'react-hotkeys-hook';

export interface ShortcutConfig {
  key: string;
  description: string;
  action: () => void;
  scope?: string;
}

// 全局快捷键配置
export const globalShortcuts: ShortcutConfig[] = [
  // 对话相关
  { key: 'ctrl+enter', description: '发送消息', action: () => {}, scope: 'chat' },
  { key: 'escape', description: '取消/关闭', action: () => {}, scope: 'global' },
  { key: 'ctrl+n', description: '新建会话', action: () => {}, scope: 'global' },
  { key: 'ctrl+/', description: '打开快捷键帮助', action: () => {}, scope: 'global' },
  
  // 导航
  { key: 'ctrl+1', description: '跳转到对话', action: () => {}, scope: 'global' },
  { key: 'ctrl+2', description: '跳转到审批', action: () => {}, scope: 'global' },
  { key: 'ctrl+3', description: '跳转到工具', action: () => {}, scope: 'global' },
  { key: 'ctrl+4', description: '跳转到监控', action: () => {}, scope: 'global' },
  
  // 搜索
  { key: 'ctrl+k', description: '全局搜索', action: () => {}, scope: 'global' },
  { key: 'ctrl+f', description: '页面内搜索', action: () => {}, scope: 'local' },
];

// 快捷键 Hook
export function useKeyboardShortcuts(shortcuts: ShortcutConfig[]) {
  const { push } = useNavigate();
  const [helpOpen, setHelpOpen] = useState(false);
  
  // 合并默认快捷键
  const allShortcuts = [...globalShortcuts, ...shortcuts];
  
  // 注册快捷键
  useHotkeys('ctrl+n', () => {
    window.location.href = '/chat/new';
  }, { preventDefault: true });
  
  useHotkeys('ctrl+/', () => {
    setHelpOpen(true);
  }, { preventDefault: true });
  
  useHotkeys('ctrl+1', () => push('/chat'), { preventDefault: true });
  useHotkeys('ctrl+2', () => push('/approval'), { preventDefault: true });
  useHotkeys('ctrl+3', () => push('/tools'), { preventDefault: true });
  useHotkeys('ctrl+4', () => push('/dashboard'), { preventDefault: true });
  
  useHotkeys('escape', () => {
    // 关闭当前模态框或返回
  }, { preventDefault: true });
  
  return { helpOpen, setHelpOpen, shortcuts: allShortcuts };
}

// 快捷键帮助弹窗
export function ShortcutHelpModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const shortcutsByScope = useMemo(() => {
    return globalShortcuts.reduce((acc, s) => {
      const scope = s.scope || 'global';
      if (!acc[scope]) acc[scope] = [];
      acc[scope].push(s);
      return acc;
    }, {} as Record<string, ShortcutConfig[]>);
  }, []);
  
  const scopeLabels: Record<string, string> = {
    global: '全局',
    chat: '对话',
    local: '当前页面',
  };
  
  return (
    <Modal
      title="快捷键帮助"
      open={open}
      onCancel={onClose}
      footer={null}
      width={500}
    >
      {Object.entries(shortcutsByScope).map(([scope, items]) => (
        <div key={scope} className="mb-4">
          <h3 className="font-bold text-gray-500 mb-2">{scopeLabels[scope] || scope}</h3>
          <table className="w-full">
            <tbody>
              {items.map((item, index) => (
                <tr key={index} className="border-b border-gray-100">
                  <td className="py-2">
                    <kbd className="px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded text-sm font-mono">
                      {item.key}
                    </kbd>
                  </td>
                  <td className="py-2 text-gray-600 dark:text-gray-400">
                    {item.description}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </Modal>
  );
}

// 在根组件中使用
function App() {
  const [helpOpen, setHelpOpen] = useState(false);
  
  return (
    <>
      {/* ... */}
      <ShortcutHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
    </>
  );
}
```

---

## 9. 测试策略

### 9.1 单元测试

```typescript
// tests/unit/hooks/usePermission.test.ts

import { describe, it, expect, beforeEach } from 'vitest';
import { usePermission, Permissions, RolePermissions } from '@/hooks/usePermission';
import { useAuthStore } from '@/stores/authStore';

describe('usePermission', () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: {
        id: 'test-user',
        username: 'test',
        email: 'test@example.com',
        roles: ['operator'],
        permissions: [],
      },
      isAuthenticated: true,
    });
  });
  
  it('should return true for operator with approval:read permission', () => {
    const { hasPermission } = usePermission();
    expect(hasPermission(Permissions.APPROVAL_READ)).toBe(true);
  });
  
  it('should return false for operator with tool:delete permission', () => {
    const { hasPermission } = usePermission();
    expect(hasPermission(Permissions.TOOL_DELETE)).toBe(false);
  });
  
  it('should return true for admin with all permissions', () => {
    useAuthStore.setState({
      user: {
        id: 'admin-user',
        username: 'admin',
        email: 'admin@example.com',
        roles: ['admin'],
        permissions: [],
      },
    });
    
    const { hasPermission } = usePermission();
    expect(hasPermission(Permissions.TOOL_DELETE)).toBe(true);
  });
});
```

### 9.2 E2E 测试

```typescript
// tests/e2e/chat.spec.ts

import { test, expect } from '@playwright/test';

// 使用环境变量配置测试账号
const TEST_USER = {
  admin: { username: process.env.E2E_ADMIN_USER || 'admin', password: process.env.E2E_ADMIN_PASS || 'admin123' },
  viewer: { username: process.env.E2E_VIEWER_USER || 'viewer', password: process.env.E2E_VIEWER_PASS || 'viewer123' },
};

test.describe('Chat Flow', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('[name="username"]', TEST_USER.admin.username);
    await page.fill('[name="password"]', TEST_USER.admin.password);
    await page.click('button[type="submit"]');
    await page.waitForURL('/');
  });
  
  test('should send message and receive streaming response', async ({ page }) => {
    await page.goto('/chat/new');
    
    // 发送消息
    await page.fill('[data-testid="chat-input"]', '你好，请帮我查询订单状态');
    await page.click('[data-testid="send-button"]');
    
    // 等待流式响应
    await expect(page.locator('[data-testid="assistant-message"]')).toBeVisible({
      timeout: 10000,
    });
    
    // 验证步骤可视化
    await expect(page.locator('[data-testid="step-visualizer"]')).toBeVisible();
  });
  
  test('should cancel streaming message', async ({ page }) => {
    await page.goto('/chat/new');
    
    await page.fill('[data-testid="chat-input"]', '写一篇长文章');
    await page.click('[data-testid="send-button"]');
    
    // 等待开始流式
    await page.waitForSelector('[data-testid="cancel-button"]');
    
    // 取消
    await page.click('[data-testid="cancel-button"]');
    
    // 验证已停止
    await expect(page.locator('[data-testid="cancel-button"]')).not.toBeVisible();
  });
  
  test('should handle network error gracefully', async ({ page, context }) => {
    await page.goto('/chat/new');
    
    // 模拟网络断开
    await context.setOffline(true);
    
    await page.fill('[data-testid="chat-input"]', '测试消息');
    await page.click('[data-testid="send-button"]');
    
    // 验证错误提示
    await expect(page.locator('.ant-message-error')).toBeVisible({ timeout: 5000 });
    
    // 恢复网络
    await context.setOffline(false);
  });
  
  test('should handle timeout error', async ({ page }) => {
    // 模拟慢速响应
    await page.route('**/api/v1/chat/completions', async (route) => {
      await new Promise((r) => setTimeout(r, 35000)); // 超过 30s
      route.abort();
    });
    
    await page.goto('/chat/new');
    await page.fill('[data-testid="chat-input"]', '测试超时');
    await page.click('[data-testid="send-button"]');
    
    // 验证超时错误
    await expect(page.locator('.ant-message-error')).toBeVisible({ timeout: 35000 });
  });
});

// tests/e2e/permissions.spec.ts - 权限边界测试
test.describe('Permission Boundaries', () => {
  test('viewer cannot access tool management', async ({ page }) => {
    // 以 viewer 登录
    await page.goto('/login');
    await page.fill('[name="username"]', TEST_USER.viewer.username);
    await page.fill('[name="password"]', TEST_USER.viewer.password);
    await page.click('button[type="submit"]');
    
    // 尝试访问工具管理
    await page.goto('/tools/register');
    
    // 应被重定向到 403 页面或首页
    await expect(page).not.toHaveURL('/tools/register');
  });
  
  test('viewer cannot approve requests', async ({ page }) => {
    // 以 viewer 登录
    await page.goto('/login');
    await page.fill('[name="username"]', TEST_USER.viewer.username);
    await page.fill('[name="password"]', TEST_USER.viewer.password);
    await page.click('button[type="submit"]');
    
    // 访问审批列表
    await page.goto('/approval');
    
    // 审批按钮应不存在
    await expect(page.locator('[data-testid="approve-button"]')).not.toBeVisible();
  });
});
```

---

### 9.3 国际化支持

> 设计原则：错误消息与后端 `user_message` 对齐，支持中英文切换。

```typescript
// src/i18n/config.ts
import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import zh from './locales/zh.json';
import en from './locales/en.json';

i18n.use(initReactI18next).init({
  resources: { zh, en },
  lng: localStorage.getItem('lang') || 'zh',
  fallbackLng: 'zh',
  interpolation: { escapeValue: false },
});

export default i18n;

// src/i18n/locales/zh.json
{
  "error": {
    "10001": "请求参数无效，请检查输入",
    "10002": "登录已过期，请重新登录",
    "10003": "您没有权限执行此操作",
    "20001": "任务执行步骤过多，已自动终止",
    "30001": "AI 服务暂时不可用，请稍后再试"
  },
  "chat": {
    "placeholder": "输入消息...",
    "send": "发送",
    "cancel": "取消"
  }
}

// src/i18n/locales/en.json
{
  "error": {
    "10001": "Invalid request, please check your input",
    "10002": "Session expired, please login again",
    "10003": "You don't have permission for this action",
    "20001": "Task exceeded max steps, auto-terminated",
    "30001": "AI service unavailable, please try later"
  }
}
```

```tsx
// 语言切换组件
import { useTranslation } from 'react-i18next';

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  
  const toggle = () => {
    const next = i18n.language === 'zh' ? 'en' : 'zh';
    i18n.changeLanguage(next);
    localStorage.setItem('lang', next);
  };
  
  return (
    <Button onClick={toggle}>
      {i18n.language === 'zh' ? 'EN' : '中文'}
    </Button>
  );
}
```

---

## 10. 部署配置

### 10.1 环境变量

```bash
# .env.production

# API 地址
VITE_API_BASE_URL=https://api.example.com/api/v1

# WebSocket 地址
VITE_WS_URL=wss://api.example.com/ws

# 环境
VITE_ENV=production

# Sentry DSN（可选）
VITE_SENTRY_DSN=https://xxx@sentry.io/xxx
```

### 10.2 Docker 构建

```dockerfile
# Dockerfile

FROM node:20-alpine AS builder

WORKDIR /app

# 安装 pnpm
RUN npm install -g pnpm

# 复制依赖文件
COPY package.json pnpm-lock.yaml ./

# 安装依赖
RUN pnpm install --frozen-lockfile

# 复制源码
COPY . .

# 构建
RUN pnpm build

# 生产镜像
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### 10.3 Nginx 配置

```nginx
# nginx.conf

server {
    listen 80;
    server_name _;
    
    root /usr/share/nginx/html;
    index index.html;
    
    # 安全头配置
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https:; frame-ancestors 'none'" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # SPA 路由
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # API 代理
    location /api/ {
        proxy_pass http://gateway-java:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # SSE 支持
    location /api/v1/chat/completions {
        proxy_pass http://gateway-java:8080/api/v1/chat/completions;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding off;
        proxy_read_timeout 300s; # 长连接超时
    }
    
    # WebSocket 代理
    location /ws {
        proxy_pass http://gateway-java:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s; # WebSocket 长连接
    }
    
    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # 安全：禁止访问隐藏文件
    location ~ /\. {
        deny all;
    }
}
```

---

## 11. 实施路线图

| 阶段 | 时间 | 交付物 | 验收标准 |
|------|------|--------|----------|
| **Phase 1: 基础框架** | 第 1-2 周 | 项目搭建、路由、认证、布局 | 登录可用、路由守卫生效 |
| **Phase 2: 对话功能** | 第 3-4 周 | Chat 界面、SSE 流式、步骤可视化 | 对话流程跑通、流式输出正常 |
| **Phase 3: 管理功能** | 第 5-6 周 | 审批、工具管理、审计日志 | 管理员可操作、权限控制正确 |
| **Phase 4: 监控面板** | 第 7-8 周 | Dashboard、图表、实时更新 | 数据展示正确、图表渲染正常 |
| **Phase 5: 优化上线** | 第 9-10 周 | 性能优化、E2E 测试、部署 | Lighthouse ≥ 90、测试覆盖 ≥ 80% |

---

## 12. 附录

### 12.1 相关文档索引

| 文档 | 内容 |
|------|------|
| [02-communication-contracts.md](./02-communication-contracts.md) | API 契约、错误码 |
| [03-security-specification.md](./03-security-specification.md) | 认证、权限、多租户 |
| [04-data-design-complete.md](./04-data-design-complete.md) | 数据模型 |
| [05-performance-optimization.md](./05-performance-optimization.md) | SSE、Fast Path |
| [07-scalability-patterns.md](./07-scalability-patterns.md) | 多租户、配额 |

### 12.2 技术栈版本锁定

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-router": "^1.30.0",
    "@tanstack/react-query": "^5.28.0",
    "@tanstack/react-virtual": "^3.0.0",
    "zustand": "^4.5.0",
    "antd": "^5.15.0",
    "tailwindcss": "^3.4.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.0",
    "lucide-react": "^0.344.0",
    "react-hook-form": "^7.51.0",
    "react-i18next": "^14.0.0",
    "@sentry/react": "^7.100.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.4.0",
    "@playwright/test": "^1.42.0",
    "openapi-typescript": "^6.7.0",
    "eslint": "^8.57.0",
    "prettier": "^3.2.0"
  }
}
```

### 12.3 UX 增强建议

| 缺失功能 | 建议 | 优先级 |
|----------|------|--------|
| 流式进度预估 | 显示当前步骤 + 剩余预估时间 | P2 |
| 审批过期提醒 | WebSocket 推送 + 前端倒计时显示 | P1 |
| 对话历史搜索 | 添加历史消息全文搜索功能 | P2 |
| 工具变更记录 | 工具版本 diff 和变更日志展示 | P3 |
| 消息引用回复 | 支持引用特定消息进行回复 | P3 |
| 快捷键支持 | Ctrl+Enter 发送、Esc 取���等 | P2 |
| 深色模式切换 | 基于系统偏好或手动切换 | P1 |

```tsx
// 审批过期倒计时示例
function ApprovalExpiryTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState('');
  
  useEffect(() => {
    const timer = setInterval(() => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining('已过期');
        clearInterval(timer);
      } else {
        const hours = Math.floor(diff / 3600000);
        const minutes = Math.floor((diff % 3600000) / 60000);
        setRemaining(`${hours}小时${minutes}分钟`);
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [expiresAt]);
  
  return <Tag color={remaining === '已过期' ? 'red' : 'blue'}>{remaining}</Tag>;
}
```

### 12.4 通用 Hooks 实现

#### 防抖 Hook

```typescript
// src/hooks/useDebounce.ts

import { useState, useEffect, useRef } from 'react';

export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState(value);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  
  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    
    timerRef.current = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);
    
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [value, delay]);
  
  return debouncedValue;
}

// 使用示例：搜索输入
function SearchInput({ onSearch }: { onSearch: (query: string) => void }) {
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 500);
  
  useEffect(() => {
    if (debouncedQuery) {
      onSearch(debouncedQuery);
    }
  }, [debouncedQuery, onSearch]);
  
  return <Input placeholder="搜索..." value={query} onChange={(e) => setQuery(e.target.value)} />;
}
```

#### 节流 Hook

```typescript
// src/hooks/useThrottle.ts

import { useCallback, useRef } from 'react';

export function useThrottle<T extends (...args: unknown[]) => void>(
  callback: T,
  delay: number = 300
): T {
  const lastCallRef = useRef(0);
  
  return useCallback((...args: unknown[]) => {
    const now = Date.now();
    if (now - lastCallRef.current >= delay) {
      lastCallRef.current = now;
      callback(...args);
    }
  }, [callback, delay]) as T;
}
```

### 12.5 核心组件完整实现

#### InputBox 组件

```tsx
// src/components/chat/InputBox.tsx

import { useState, useRef, KeyboardEvent } from 'react';
import { Button, Input, Tooltip } from 'antd';
import { Send, Square, Mic, Paperclip } from 'lucide-react';

interface InputBoxProps {
  onSubmit: (message: string, attachments?: File[]) => void;
  onCancel: () => void;
  isStreaming: boolean;
  disabled?: boolean;
  placeholder?: string;
  maxLength?: number;
}

export function InputBox({
  onSubmit,
  onCancel,
  isStreaming,
  disabled = false,
  placeholder = '输入消息，按 Enter 发送，Shift+Enter 换行...',
  maxLength = 4000,
}: InputBoxProps) {
  const [message, setMessage] = useState('');
  const [attachments, setAttachments] = useState<File[]>([]);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const handleSubmit = () => {
    const trimmed = message.trim();
    if (!trimmed && attachments.length === 0) return;
    if (disabled) return;
    
    onSubmit(trimmed, attachments);
    setMessage('');
    setAttachments([]);
  };
  
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };
  
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    setAttachments((prev) => [...prev, ...files]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };
  
  const handleRemoveFile = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  };
  
  const charCount = message.length;
  const isOverLimit = charCount > maxLength;
  
  return (
    <div className="flex flex-col gap-2 p-4 border-t bg-white dark:bg-gray-900">
      {/* 附件预览 */}
      {attachments.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {attachments.map((file, index) => (
            <Tag
              key={index}
              closable
              onClose={() => handleRemoveFile(index)}
              className="flex items-center gap-1"
            >
              <Paperclip className="w-3 h-3" />
              {file.name}
            </Tag>
          ))}
        </div>
      )}
      
      {/* 输入区域 */}
      <div className="flex items-end gap-2">
        {/* 附件按钮 */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileSelect}
        />
        <Tooltip title="添加附件">
          <Button
            type="text"
            icon={<Paperclip className="w-5 h-5" />}
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled}
          />
        </Tooltip>
        
        {/* 文本输入 */}
        <div className="flex-1 relative">
          <Input.TextArea
            ref={inputRef}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            autoSize={{ minRows: 1, maxRows: 6 }}
            className={isOverLimit ? 'border-red-500' : ''}
            aria-label="消息输入框"
          />
          {/* 字数统计 */}
          <div className={`absolute bottom-1 right-2 text-xs ${isOverLimit ? 'text-red-500' : 'text-gray-400'}`}>
            {charCount}/{maxLength}
          </div>
        </div>
        
        {/* 发送/取消按钮 */}
        {isStreaming ? (
          <Tooltip title="停止生成">
            <Button
              type="primary"
              danger
              icon={<Square className="w-5 h-5" />}
              onClick={onCancel}
              aria-label="停止生成"
            />
          </Tooltip>
        ) : (
          <Tooltip title="发送消息 (Enter)">
            <Button
              type="primary"
              icon={<Send className="w-5 h-5" />}
              onClick={handleSubmit}
              disabled={disabled || (!message.trim() && attachments.length === 0) || isOverLimit}
              aria-label="发送消息"
            />
          </Tooltip>
        )}
      </div>
    </div>
  );
}
```

#### MessageItem 组件

```tsx
// src/components/chat/MessageItem.tsx

import { useState } from 'react';
import { Button, Dropdown, Tooltip, Typography } from 'antd';
import { Copy, ThumbsUp, ThumbsDown, RotateCcw, MoreHorizontal } from 'lucide-react';
import type { Message } from '@/stores/chatStore';

interface MessageItemProps {
  message: Message;
  onRetry?: () => void;
  onFeedback?: (type: 'positive' | 'negative') => void;
}

export function MessageItem({ message, onRetry, onFeedback }: MessageItemProps) {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';
  
  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  
  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
    });
  };
  
  return (
    <div
      className={`flex gap-3 p-4 ${isUser ? 'flex-row-reverse' : ''}`}
      role="article"
      aria-label={`${isUser ? '用户' : '助手'}消息`}
    >
      {/* 头像 */}
      <div
        className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
          isUser ? 'bg-blue-500' : 'bg-gray-200 dark:bg-gray-700'
        }`}
        aria-hidden="true"
      >
        {isUser ? (
          <span className="text-white text-sm font-medium">U</span>
        ) : (
          <span className="text-gray-600 dark:text-gray-300 text-sm">AI</span>
        )}
      </div>
      
      {/* 消息内容 */}
      <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : ''}`}>
        {/* 时间戳 */}
        <div className={`text-xs text-gray-400 mb-1 ${isUser ? 'text-right' : ''}`}>
          {formatTime(message.created_at)}
          {message.is_offline && <Tag color="orange">离线</Tag>}
        </div>
        
        {/* 消息气泡 */}
        <div
          className={`inline-block p-3 rounded-lg ${
            isUser
              ? 'bg-blue-500 text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100'
          }`}
        >
          <Typography.Paragraph
            className="m-0 whitespace-pre-wrap break-words"
            copyable={false}
          >
            {message.content}
          </Typography.Paragraph>
        </div>
        
        {/* 操作按钮 */}
        {!isUser && (
          <div className="flex gap-1 mt-2 opacity-0 hover:opacity-100 transition-opacity">
            <Tooltip title="复制">
              <Button
                type="text"
                size="small"
                icon={<Copy className="w-4 h-4" />}
                onClick={handleCopy}
              >
                {copied ? '已复制' : ''}
              </Button>
            </Tooltip>
            <Tooltip title="有帮助">
              <Button
                type="text"
                size="small"
                icon={<ThumbsUp className="w-4 h-4" />}
                onClick={() => onFeedback?.('positive')}
              />
            </Tooltip>
            <Tooltip title="没帮助">
              <Button
                type="text"
                size="small"
                icon={<ThumbsDown className="w-4 h-4" />}
                onClick={() => onFeedback?.('negative')}
              />
            </Tooltip>
            {onRetry && (
              <Tooltip title="重新生成">
                <Button
                  type="text"
                  size="small"
                  icon={<RotateCcw className="w-4 h-4" />}
                  onClick={onRetry}
                />
              </Tooltip>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

### 12.6 审计日志导出

```tsx
// src/routes/audit/index.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Table, Button, DatePicker, Select, message, Spin } from 'antd';
import { Download, FileExcel } from 'lucide-react';
import api from '@/services/api';
import { usePermission, Permissions } from '@/hooks/usePermission';

export const Route = createFileRoute('/audit/')({
  component: AuditPage,
});

function AuditPage() {
  const { hasPermission } = usePermission();
  const [filters, setFilters] = useState<AuditQueryParams>({
    page_number: 1,
    page_size: 20,
  });
  
  // 查询审计日志
  const { data, isLoading } = useQuery({
    queryKey: ['audit', filters],
    queryFn: () => api.get<{ items: AuditEvent[]; total_count: number }>('/audit/events', {
      params: filters,
    }).then((r) => r.data),
  });
  
  // 导出审计日志
  const exportMutation = useMutation({
    mutationFn: async (params: AuditQueryParams & { format: 'csv' | 'json' }) => {
      const response = await api.get('/audit/events/export', {
        params,
        responseType: 'blob',
      });
      return response.data;
    },
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit-export-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('导出成功');
    },
    onError: () => {
      message.error('导出失败，请稍后重试');
    },
  });
  
  const columns = [
    { title: '时间', dataIndex: 'created_at', width: 160, render: (t: string) => new Date(t).toLocaleString() },
    { title: '事件类型', dataIndex: 'event_type', width: 140 },
    { title: '严重级别', dataIndex: 'severity', width: 80, render: (s: string) => <Tag color={severityColors[s]}>{s}</Tag> },
    { title: '用户', dataIndex: 'user_id', width: 120 },
    { title: '资源', dataIndex: 'resource_type', width: 120 },
    { title: '操作', dataIndex: 'action', width: 120 },
    { title: '来源服务', dataIndex: 'source_service', width: 100 },
  ];
  
  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">审计日志</h1>
        {hasPermission(Permissions.AUDIT_EXPORT) && (
          <Dropdown
            menu={{
              items: [
                { key: 'csv', label: 'CSV 格式', icon: <FileExcel className="w-4 h-4" /> },
                { key: 'json', label: 'JSON 格式' },
              ],
              onClick: ({ key }) => {
                exportMutation.mutate({ ...filters, format: key as 'csv' | 'json' });
              },
            }}
          >
            <Button type="primary" icon={<Download className="w-4 h-4" />} loading={exportMutation.isPending}>
              导出
            </Button>
          </Dropdown>
        )}
      </div>
      
      {/* 筛选器 */}
      <div className="flex gap-4 mb-4 flex-wrap">
        <DatePicker.RangePicker
          onChange={(dates) => setFilters((f) => ({
            ...f,
            start_time: dates?.[0]?.toISOString(),
            end_time: dates?.[1]?.toISOString(),
          }))}
        />
        <Select
          placeholder="事件类型"
          allowClear
          onChange={(v) => setFilters((f) => ({ ...f, event_type: v }))}
          options={eventTypeOptions}
          style={{ width: 150 }}
        />
        <Select
          placeholder="严重级别"
          allowClear
          onChange={(v) => setFilters((f) => ({ ...f, severity: v }))}
          options={['info', 'warn', 'error', 'critical'].map((s) => ({ label: s, value: s }))}
          style={{ width: 120 }}
        />
      </div>
      
      <Table
        columns={columns}
        dataSource={data?.items}
        loading={isLoading}
        rowKey="id"
        pagination={{
          current: filters.page_number,
          pageSize: filters.page_size,
          total: data?.total_count,
          onChange: (page, size) => setFilters((f) => ({ ...f, page_number: page, page_size: size })),
        }}
      />
    </div>
  );
}
```

### 12.7 无障碍访问 (Accessibility)

> **设计原则**：遵循 WCAG 2.1 AA 标准，确保键盘可访问、屏幕阅读器友好。

```tsx
// 无障碍设计规范

/** 1. 语义化 HTML */
// ✅ 正确：使用语义化标签
<nav aria-label="主导航">
  <ul>
    <li><a href="/chat">对话</a></li>
  </ul>
</nav>

// ❌ 错误：滥用 div
<div onClick={navigate}><span>对话</span></div>

/** 2. ARIA 属性 */
<Button
  aria-label="发送消息"
  aria-describedby="send-tooltip"
  aria-disabled={isDisabled}
>
  <SendIcon aria-hidden="true" />
</Button>

/** 3. 键盘导航 */
function handleKeyDown(e: KeyboardEvent) {
  // Tab 导航
  if (e.key === 'Tab') {
    // 管理焦点
  }
  // Enter 激活
  if (e.key === 'Enter' && !e.shiftKey) {
    handleSubmit();
  }
  // Escape 取消
  if (e.key === 'Escape') {
    closeModal();
  }
  // 箭头键导航列表
  if (['ArrowUp', 'ArrowDown'].includes(e.key)) {
    navigateList(e.key === 'ArrowUp' ? -1 : 1);
  }
}

/** 4. 焦点管理 */
// 对话打开时聚焦到输入框
useEffect(() => {
  if (isOpen) {
    inputRef.current?.focus();
  }
}, [isOpen]);

// 焦点陷阱（模态框）
import { FocusTrap } from '@react-aria/focus';
<FocusTrap>
  <Modal>...</Modal>
</FocusTrap>

/** 5. 颜色对比度 */
// 确保文字与背景对比度 ≥ 4.5:1（普通文字）或 ≥ 3:1（大文字）
// 使用工具验证：https://webaim.org/resources/contrastchecker/

/** 6. 表单标签 */
<label htmlFor="message-input">消息内容</label>
<Input id="message-input" aria-required="true" />

/** 7. 状态通知 */
// 使用 aria-live 通知动态内容变化
<div aria-live="polite" aria-atomic="true">
  {statusMessage}
</div>

// 加载状态
<Button loading aria-busy="true">
  处理中
</Button>
```

### 12.8 响应式设计

```css
/* tailwind.config.ts 响应式断点 */
export default {
  theme: {
    screens: {
      'sm': '640px',   // 手机横屏
      'md': '768px',   // 平板
      'lg': '1024px',  // 小桌面
      'xl': '1280px',  // 大桌面
      '2xl': '1536px', // 超大屏
    },
  },
};
```

```tsx
// 响应式布局示例

// 侧边栏：移动端折叠
function ResponsiveSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const isMobile = useMediaQuery('(max-width: 768px)');
  
  useEffect(() => {
    setCollapsed(isMobile);
  }, [isMobile]);
  
  return (
    <aside className={`
      fixed inset-y-0 left-0 z-50
      bg-white dark:bg-gray-900
      transition-all duration-300
      ${collapsed ? 'w-16' : 'w-64'}
      md:relative md:w-64
    `}>
      {/* ... */}
    </aside>
  );
}

// 表格：移动端卡片式
function ResponsiveTable({ data }: { data: ToolDefinition[] }) {
  const isMobile = useMediaQuery('(max-width: 768px)');
  
  if (isMobile) {
    return (
      <div className="flex flex-col gap-4">
        {data.map((item) => (
          <Card key={item.name}>
            <div className="flex justify-between">
              <span className="font-medium">{item.name}</span>
              <Tag color={statusColors[item.status]}>{item.status}</Tag>
            </div>
            <p className="text-sm text-gray-500 mt-2">{item.description}</p>
          </Card>
        ))}
      </div>
    );
  }
  
  return <Table columns={columns} dataSource={data} />;
}
```

### 12.9 深色模式

```typescript
// src/stores/uiStore.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

type Theme = 'light' | 'dark' | 'system';

interface UIState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme: 'system',
      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
      },
    }),
    {
      name: 'ui-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ theme: state.theme }),
    }
  )
);

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  const isDark = theme === 'dark' || 
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  
  root.classList.toggle('dark', isDark);
}

// 初始化时应用主题
useEffect(() => {
  applyTheme(useUIStore.getState().theme);
  
  // 监听系统主题变化
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const handler = () => {
    if (useUIStore.getState().theme === 'system') {
      applyTheme('system');
    }
  };
  media.addEventListener('change', handler);
  return () => media.removeEventListener('change', handler);
}, []);
```

```tsx
// 主题切换组件
import { Sun, Moon, Monitor } from 'lucide-react';

const themeOptions = [
  { value: 'light', label: '浅色', icon: <Sun className="w-4 h-4" /> },
  { value: 'dark', label: '深色', icon: <Moon className="w-4 h-4" /> },
  { value: 'system', label: '跟随系统', icon: <Monitor className="w-4 h-4" /> },
];

export function ThemeSwitcher() {
  const { theme, setTheme } = useUIStore();
  
  return (
    <Select
      value={theme}
      onChange={setTheme}
      options={themeOptions}
      optionRender={(option) => (
        <div className="flex items-center gap-2">
          {option.data.icon}
          {option.data.label}
        </div>
      )}
      style={{ width: 120 }}
      aria-label="主题设置"
    />
  );
}
```
      }
    }, 1000);
    return () => clearInterval(timer);
  }, [expiresAt]);
  
  return <Tag color={remaining === '已过期' ? 'red' : 'blue'}>{remaining}</Tag>;
}
```
