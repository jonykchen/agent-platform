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
  stream?: boolean;
  enabled_tools?: string[];
  model_override?: string;
}

/** SSE 流式响应块 */
export interface ChatCompletionChunk {
  chunk_id: string;
  delta_content: string;
  is_final: boolean;
  finish_reason: FinishReason;
  usage?: TokenUsage;
  step_info?: AgentStepInfo;
}

export type FinishReason = 'stop' | 'tool_call' | 'length' | 'error';

/** Token 用量 */
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
  thinking?: string;
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
  error_code?: number;
  model_used?: string;
  total_tokens: number;
  total_cost_usd: number;
  duration_ms?: number;
  started_at: string;
  completed_at?: string;
}

export type RunStatus = 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';

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

/** 消息 */
export interface Message {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
  is_offline?: boolean;
}