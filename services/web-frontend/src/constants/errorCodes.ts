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

  // 认证
  [ErrorCode.ERR_AUTH_INVALID_CREDENTIALS]: '用户名或密码错误',
  [ErrorCode.ERR_AUTH_TOKEN_EXPIRED]: '登录已过期，请重新登录',
  [ErrorCode.ERR_AUTH_TOKEN_INVALID]: '认证信息无效',
  [ErrorCode.ERR_AUTH_USER_NOT_FOUND]: '用户不存在',
};

/** 获取用户友好的错误消息 */
export function getUserMessage(error: { code: ErrorCode; user_message?: string }): string {
  if (error.user_message) return error.user_message;
  return ErrorMessageMap[error.code] || '操作失败，请稍后再试';
}