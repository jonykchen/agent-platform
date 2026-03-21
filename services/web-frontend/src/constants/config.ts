/** 应用配置常量 */
export const APP_CONFIG = {
  APP_NAME: 'Agent Platform',
  APP_VERSION: '0.1.0',

  // API 配置
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  WS_URL: import.meta.env.VITE_WS_URL || '/ws',

  // Token 配置
  TOKEN_REFRESH_THRESHOLD_SECONDS: 60, // Token 过期前 60 秒刷新

  // 分页配置
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,

  // 对话配置
  MAX_MESSAGE_LENGTH: 4000,
  MAX_HISTORY_MESSAGES: 100,
  VIRTUAL_SCROLL_OVERSCAN: 5,

  // SSE 配置
  SSE_RETRY_ATTEMPTS: 3,
  SSE_RETRY_DELAY_MS: 1000,

  // WebSocket 配置
  WS_HEARTBEAT_INTERVAL_MS: 30000,
  WS_RECONNECT_ATTEMPTS: 5,
  WS_RECONNECT_DELAY_MS: 3000,

  // 缓存配置
  QUERY_STALE_TIME_MS: 5 * 60 * 1000, // 5 分钟
  QUERY_GC_TIME_MS: 30 * 60 * 1000, // 30 分钟

  // 文件上传配置
  MAX_FILE_SIZE_MB: 50,
  MAX_FILES_PER_UPLOAD: 10,
} as const;