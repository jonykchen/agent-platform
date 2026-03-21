/**
 * 生成请求 ID (简单实现)
 */
export function generateRequestId(): string {
  const timestamp = Date.now().toString(36);
  const random = Math.random().toString(36).substring(2, 10);
  return `req_${timestamp}_${random}`;
}

/**
 * 生成追踪 ID
 */
export function generateTraceId(): string {
  const random = Math.random().toString(36).substring(2, 18);
  return `trace_${random}`;
}