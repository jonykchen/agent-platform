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
  error_code?: number;
  error_message?: string;
  approval_id?: string;
  was_cached: boolean;
  duration_ms?: number;
  provider_latency_ms?: number;
  created_at: string;
  completed_at?: string;
}