import { notification } from 'antd';
import axios from 'axios';
import { ErrorCode, ErrorDetail, isRetryable } from '@/types/error';
import { ErrorMessageMap } from '@/constants/errorCodes';

/** 获取用户友好的错误消息 */
export function getUserMessage(error: { code: ErrorCode; user_message?: string }): string {
  if (error.user_message) return error.user_message;
  return ErrorMessageMap[error.code] || '操作失败，请稍后再试';
}

/** API 错误统一处理 */
export function handleApiError(error: unknown, options?: { silent?: boolean }): void {
  if (options?.silent) return;

  if (axios.isAxiosError(error)) {
    const { response, code } = error;

    if (code === 'ERR_NETWORK' || !response) {
      notification.error({
        message: '网络错误',
        description: '无法连接服务器，请检查网络连接',
      });
      return;
    }

    const errorData = response.data?.error as ErrorDetail | undefined;

    if (errorData) {
      const userMsg = getUserMessage(errorData);
      if (response.status === 401) return;

      notification.error({
        message: '操作失败',
        description: userMsg,
        duration: errorData.code === ErrorCode.ERR_RATE_LIMITED ? 10 : 4.5,
      });
      return;
    }

    notification.error({
      message: '请求失败',
      description: `HTTP ${response.status}: ${response.statusText}`,
    });
    return;
  }

  notification.error({
    message: '未知错误',
    description: error instanceof Error ? error.message : '请刷新页面重试',
  });
}

/** 判断错误是否可重试 */
export function shouldRetry(error: unknown): boolean {
  if (axios.isAxiosError(error)) {
    const errorData = error.response?.data?.error as ErrorDetail | undefined;
    if (errorData?.code) {
      return isRetryable(errorData.code);
    }
    return error.code === 'ERR_NETWORK' || error.response?.status === 503;
  }
  return false;
}