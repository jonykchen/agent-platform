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
| 对话流式输出 | EventSource (SSE) | 原生 API、自动重连、单向推送 |
| 审批通知推送 | WebSocket | 双向通信、实时通知、在线状态 |
| 连接状态管理 | 自定义 Hook | 统一处理断线重连、心跳检测 |

### 2.3 工具链

| 工具 | 用途 |
|------|------|
| **pnpm** | 包管理（Monorepo 支持） |
| **Turborepo** | Monorepo 构建（可选） |
| **ESLint** | 代码检查 |
| **Prettier** | 代码格式化 |
| **Vitest** | 单元测试 |
| **Playwright** | E2E 测试 |
| **Storybook** | 组件文档（可选） |

### 2.4 目录结构

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
    │   │   │   ├── index.tsx        # 对话列表
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
    │   │   ├── dashboard/
    │   │   │   └── index.tsx        # 监控面板
    │   │   └── login.tsx            # 登录页
    │   │
    │   ├── components/              # 共享组件
    │   │   ├── ui/                  # 基础 UI 组件（Button/Input/Modal...）
    │   │   ├── chat/                # 对话相关组件
    │   │   │   ├── MessageList.tsx
    │   │   │   ├── MessageItem.tsx
    │   │   │   ├── InputBox.tsx
    │   │   │   ├── StepVisualizer.tsx
    │   │   │   └── ToolCallCard.tsx
    │   │   ├── approval/            # 审批相关组件
    │   │   │   ├── ApprovalCard.tsx
    │   │   │   └── ApprovalTimeline.tsx
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
    │   │   └── usePermission.ts     # 权限检查
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

### 4.2 RBAC 权限检查

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

---

## 5. SSE 流式通信

> 与 [05-performance-optimization.md](./05-performance-optimization.md) Fast Path 设计一致

### 5.1 SSE Hook 实现

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
  
  const eventSourceRef = useRef<EventSource | null>(null);
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
    
    // 构建 URL（带 query params，因为 EventSource 不支持 body）
    const params = new URLSearchParams();
    if (body) {
      params.set('body', JSON.stringify(body));
    }
    const fullUrl = `${url}?${params.toString()}`;
    
    // EventSource 不支持自定义 Header，使用 fetch + ReadableStream 替代
    fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${accessToken}`,
        'X-Tenant-ID': tenant?.id || '',
        'X-User-ID': user?.id || '',
      },
      body: JSON.stringify(body),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        
        setState((s) => ({ ...s, isConnected: true, isStreaming: true }));
        
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
            
            // 解析 SSE 格式: "data: {...}\n\n"
            const lines = chunk.split('\n');
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6)) as T;
                  onMessage(data);
                } catch (e) {
                  console.error('Failed to parse SSE data:', e);
                }
              }
            }
            
            return readChunk();
          });
        };
        
        return readChunk();
      })
      .catch((error) => {
        setState((s) => ({ ...s, error, isStreaming: false }));
        onError?.(error);
        
        // 自动重试
        if (retryCountRef.current < retryAttempts) {
          retryCountRef.current += 1;
          setState((s) => ({ ...s, retryCount: retryCountRef.current }));
          setTimeout(connect, retryDelay * retryCountRef.current);
        }
      });
  }, [url, body, enabled, onMessage, onError, onComplete, retryAttempts, retryDelay]);
  
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
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

### 6.1 对话界面

```tsx
// src/routes/chat/$sessionId.tsx

import { createFileRoute } from '@tanstack/react-router';
import { useState, useRef, useEffect } from 'react';
import { useChat } from '@/hooks/useChat';
import { MessageList } from '@/components/chat/MessageList';
import { InputBox } from '@/components/chat/InputBox';
import { StepVisualizer } from '@/components/chat/StepVisualizer';
import { useChatStore } from '@/stores/chatStore';

export const Route = createFileRoute('/chat/$sessionId')({
  component: ChatPage,
});

function ChatPage() {
  const { sessionId } = Route.useParams();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
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
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4">
        <MessageList messages={sessionMessages} />
        
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
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get<DashboardStats>('/dashboard/stats').then((r) => r.data),
    refetchInterval: 60000, // 每分钟刷新
  });
  
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">监控面板</h1>
      
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
      
      <Row gutter={16} className="mb-6">
        <Col span={12}>
          <Card title="平均延迟">
            <Statistic
              value={data?.avg_latency_ms}
              suffix="ms"
              loading={isLoading}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="成功率">
            <Statistic
              value={data?.success_rate}
              suffix="%"
              precision={1}
              loading={isLoading}
            />
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

---

## 8. 错误处理

### 8.1 错误码映射

```typescript
// src/utils/error.ts

import { ErrorCode } from '@/types/error';

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
  [ErrorCode.ERR_AGENT_RUN_CANCELLED]: '任务已被取消',
  [ErrorCode.ERR_AGENT_RUN_PAUSED]: '任务暂停中，等待审批',
  
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
  [ErrorCode.ERR_TOOL_TIMEOUT]: '工具执行超时',
  [ErrorCode.ERR_TOOL_DISABLED]: '该工具已被禁用',
  
  // 审批
  [ErrorCode.ERR_APPROVAL_EXPIRED]: '审批已过期',
  [ErrorCode.ERR_APPROVAL_ALREADY_REVIEWED]: '该审批已处理',
  [ErrorCode.ERR_APPROVAL_NOT_ASSIGNEE]: '您不是该审批的指定审批人',
};

/** 获取用户友好的错误消息 */
export function getUserMessage(error: { code: ErrorCode; user_message?: string }): string {
  // 优先使用后端返回的 user_message
  if (error.user_message) {
    return error.user_message;
  }
  
  // 使用映射表
  const mapped = ErrorMessageMap[error.code];
  if (mapped) {
    return mapped;
  }
  
  // 默认消息
  return '操作失败，请稍后再试';
}
```

### 8.2 全局错误边界

```tsx
// src/components/feedback/ErrorBoundary.tsx

import { Component, ErrorInfo, ReactNode } from 'react';
import { Button } from 'antd';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
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
    // 上报错误
    console.error('ErrorBoundary caught:', error, errorInfo);
    
    // 发送到监控系统
    fetch('/api/v1/errors', {
      method: 'POST',
      body: JSON.stringify({
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        url: window.location.href,
        timestamp: new Date().toISOString(),
      }),
    }).catch(console.error);
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
          <p className="text-gray-500 mb-4">
            {this.state.error?.message || '未知错误'}
          </p>
          <Button type="primary" onClick={() => window.location.reload()}>
            刷新页面
          </Button>
        </div>
      );
    }
    
    return this.props.children;
  }
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

test.describe('Chat Flow', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('[name="username"]', 'test-user');
    await page.fill('[name="password"]', 'test-password');
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
});
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
    }
    
    # WebSocket 代理
    location /ws {
        proxy_pass http://gateway-java:8080/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
    
    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
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
    "zustand": "^4.5.0",
    "antd": "^5.15.0",
    "tailwindcss": "^3.4.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.0",
    "lucide-react": "^0.344.0",
    "react-hook-form": "^7.51.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "vite": "^5.2.0",
    "vitest": "^1.4.0",
    "@playwright/test": "^1.42.0",
    "eslint": "^8.57.0",
    "prettier": "^3.2.0"
  }
}
```
