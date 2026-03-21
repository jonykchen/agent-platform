import { useCallback, useRef } from 'react';
import { useChatStore } from '@/stores/chatStore';
import { useSSE } from './useSSE';
import { useNetworkStatus } from './useNetworkStatus';
import { useAuthStore } from '@/stores/authStore';
import type { ChatCompletionChunk, Message, ChatRequest } from '@/types/chat';
import { APP_CONFIG } from '@/constants/config';

export interface UseChatOptions {
  sessionId: string;
  onComplete?: (message: Message) => void;
  onError?: (error: Error) => void;
  onStep?: (step: ChatCompletionChunk['step_info']) => void;
}

export interface SendMessageOptions {
  content: string;
  history?: ChatRequest['history'];
  options?: ChatRequest['options'];
}

export interface UseChatReturn {
  // 状态
  messages: Message[];
  isStreaming: boolean;
  streamingContent: string;
  currentSteps: ChatCompletionChunk['step_info'][];
  currentRunId: string | null;

  // 操作
  sendMessage: (options: SendMessageOptions) => void;
  cancel: () => void;
  retry: () => void;
  clearMessages: () => void;

  // 离线支持
  isOffline: boolean;
  pendingMessages: Message[];
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const { sessionId, onComplete, onError, onStep } = options;

  const {
    getSessionState,
    addMessage,
    setStreaming,
    clearStreamContent,
    setCurrentRunId,
    clearSteps,
    handleChunk,
    clearMessages: clearStoreMessages,
    addToOfflineQueue,
    removeFromOfflineQueue,
  } = useChatStore();

  const sessionState = getSessionState(sessionId);
  const { isOnline } = useNetworkStatus();
  const { accessToken, tenant, user } = useAuthStore();

  // 保存最后一次请求的引用，用于重试
  const lastRequestRef = useRef<SendMessageOptions | null>(null);

  // SSE 处理
  const sseUrl = `${APP_CONFIG.API_BASE_URL}/chat/completions`;

  const sseOptions = {
    url: sseUrl,
    enabled: false, // 手动控制
    onMessage: (chunk: ChatCompletionChunk) => {
      handleChunk(sessionId, chunk);

      if (chunk.step_info) {
        onStep?.(chunk.step_info);
      }

      if (chunk.is_final) {
        // 创建最终的 AI 消息
        const assistantMessage: Message = {
          id: `msg_${Date.now()}`,
          session_id: sessionId,
          role: 'assistant',
          content: sessionState.streamingContent,
          created_at: new Date().toISOString(),
        };

        addMessage(sessionId, assistantMessage);
        clearStreamContent(sessionId);
        clearSteps(sessionId);
        setCurrentRunId(sessionId, null);
        onComplete?.(assistantMessage);
      }
    },
    onError: (error) => {
      setStreaming(sessionId, false);
      clearSteps(sessionId);
      onError?.(error);
    },
    onComplete: () => {
      setStreaming(sessionId, false);
    },
  };

  const { connect, disconnect, retry: sseRetry, isStreaming: sseStreaming } = useSSE<ChatCompletionChunk>(sseOptions);

  // 发送消息
  const sendMessage = useCallback(
    (sendOptions: SendMessageOptions) => {
      const { content, history, options: chatOptions } = sendOptions;

      if (!content.trim()) {
        return;
      }

      lastRequestRef.current = sendOptions;

      // 检查离线状态
      if (!isOnline) {
        // 添加到离线队列
        addToOfflineQueue({
          id: `offline_${Date.now()}`,
          sessionId,
          content,
          createdAt: Date.now(),
          retryCount: 0,
        });

        // 创建用户消息标记为离线
        const offlineMessage: Message = {
          id: `msg_offline_${Date.now()}`,
          session_id: sessionId,
          role: 'user',
          content,
          created_at: new Date().toISOString(),
          is_offline: true,
        };

        addMessage(sessionId, offlineMessage);
        return;
      }

      // 创建用户消息
      const userMessage: Message = {
        id: `msg_${Date.now()}`,
        session_id: sessionId,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
      };

      addMessage(sessionId, userMessage);

      // 准备请求
      const requestBody: ChatRequest = {
        message: content,
        session_id: sessionId,
        history,
        options: {
          stream: true,
          ...chatOptions,
        },
      };

      // 更新 SSE 选项并连接
      sseOptions.body = requestBody;
      setStreaming(sessionId, true);
      clearStreamContent(sessionId);
      clearSteps(sessionId);

      connect();
    },
    [
      sessionId,
      isOnline,
      addMessage,
      setStreaming,
      clearStreamContent,
      clearSteps,
      addToOfflineQueue,
      connect,
    ]
  );

  // 取消请求
  const cancel = useCallback(() => {
    disconnect();
    setStreaming(sessionId, false);
    clearStreamContent(sessionId);
    clearSteps(sessionId);
    setCurrentRunId(sessionId, null);
  }, [disconnect, sessionId, setStreaming, clearStreamContent, clearSteps, setCurrentRunId]);

  // 重试
  const retry = useCallback(() => {
    if (lastRequestRef.current) {
      sendMessage(lastRequestRef.current);
    } else {
      sseRetry();
    }
  }, [sendMessage, sseRetry]);

  // 清空消息
  const clearMessages = useCallback(() => {
    clearStoreMessages(sessionId);
  }, [clearStoreMessages, sessionId]);

  // 离线消息列表
  const pendingMessages = sessionState.messages.filter((m) => m.is_offline);

  return {
    messages: sessionState.messages,
    isStreaming: sessionState.isStreaming,
    streamingContent: sessionState.streamingContent,
    currentSteps: sessionState.currentSteps,
    currentRunId: sessionState.currentRunId,
    sendMessage,
    cancel,
    retry,
    clearMessages,
    isOffline: !isOnline,
    pendingMessages,
  };
}

export default useChat;