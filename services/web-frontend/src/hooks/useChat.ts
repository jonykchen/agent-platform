import { useCallback, useRef, useState } from 'react';
import { useChatStore, DEFAULT_SESSION_STATE } from '@/stores/chatStore';
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

  // 使用 zustand selector 订阅会话状态，确保 store 变化时组件重新渲染
  const sessionState = useChatStore((state) => state.sessions[sessionId] || DEFAULT_SESSION_STATE);
  const {
    addMessage,
    setStreaming,
    clearStreamContent,
    setCurrentRunId,
    clearSteps,
    handleChunk,
    clearMessages: clearStoreMessages,
    addToOfflineQueue,
  } = useChatStore();

  const { isOnline } = useNetworkStatus();
  const { accessToken, tenant, user } = useAuthStore();

  // 保存最后一次请求的引用，用于重试
  const lastRequestRef = useRef<SendMessageOptions | null>(null);

  // AbortController 用于取消正在进行的 SSE 请求
  const abortControllerRef = useRef<AbortController | null>(null);

  // SSE 连接状态
  const [isConnecting, setIsConnecting] = useState(false);

  // SSE 处理函数
  const handleSSEMessage = useCallback(
    (chunk: ChatCompletionChunk) => {
      handleChunk(sessionId, chunk);

      if (chunk.step_info) {
        onStep?.(chunk.step_info);
      }

      if (chunk.is_final) {
        // 从 store 获取最新的 streamingContent
        const latestState = useChatStore.getState().getSessionState(sessionId);

        // 创建最终的 AI 消息
        const assistantMessage: Message = {
          id: `msg_${Date.now()}`,
          session_id: sessionId,
          role: 'assistant',
          content: latestState.streamingContent,
          created_at: new Date().toISOString(),
        };

        addMessage(sessionId, assistantMessage);
        clearStreamContent(sessionId);
        clearSteps(sessionId);
        setCurrentRunId(sessionId, null);
        setIsConnecting(false);
        onComplete?.(assistantMessage);
      }
    },
    [sessionId, handleChunk, onStep, addMessage, clearStreamContent, clearSteps, setCurrentRunId, onComplete]
  );

  const handleSSEError = useCallback(
    (error: Error) => {
      setStreaming(sessionId, false);
      clearSteps(sessionId);
      setIsConnecting(false);
      onError?.(error);
    },
    [sessionId, setStreaming, clearSteps, onError]
  );

  // 直接使用 fetch 发送 SSE 请求
  const sendMessage = useCallback(
    async (sendOptions: SendMessageOptions) => {
      const { content, history, options: chatOptions } = sendOptions;

      if (!content.trim()) {
        return;
      }

      // 取消正在进行的旧请求，避免多个 SSE 流并发
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }

      lastRequestRef.current = sendOptions;

      // 检查离线状态
      if (!isOnline) {
        addToOfflineQueue({
          id: `offline_${Date.now()}`,
          sessionId,
          content,
          createdAt: Date.now(),
          retryCount: 0,
        });

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

      // 构建历史消息（在添加 userMessage 之前的消息）
      const currentState = useChatStore.getState().getSessionState(sessionId);
      const recentMessages = currentState.messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-APP_CONFIG.MAX_HISTORY_MESSAGES);

      setStreaming(sessionId, true);
      clearStreamContent(sessionId);
      clearSteps(sessionId);
      setIsConnecting(true);

      // 准备请求 - 匹配后端 ChatRequest 格式
      const requestBody: Record<string, unknown> = {
        message: content,
        stream: true,
        ...chatOptions,
      };

      // 构建历史消息（扁平格式，传给后端的 history 字段）
      if (history && history.length > 0) {
        requestBody.history = history;
      } else if (recentMessages.length > 0) {
        requestBody.history = recentMessages.map((m) => ({
          role: m.role,
          content: m.content,
        }));
      }

      // 发送 SSE 请求
      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        };

        if (accessToken) {
          headers.Authorization = `Bearer ${accessToken}`;
        }
        if (tenant) {
          headers['X-Tenant-ID'] = tenant.id;
        }
        if (user) {
          headers['X-User-ID'] = user.id;
        }

        const fetchUrl = `${APP_CONFIG.API_BASE_URL}/chat/completions`;

        // SSE 流式请求必须直接请求后端，绕过 Vite 代理缓冲
        // 开发环境后端端口 8080，生产环境使用相对路径走网关
        const directSseUrl = import.meta.env.DEV
          ? `http://localhost:8080${fetchUrl}`
          : fetchUrl;

        let response: Response;
        try {
          abortControllerRef.current = new AbortController();
          response = await fetch(directSseUrl, {
            method: 'POST',
            headers,
            body: JSON.stringify(requestBody),
            signal: abortControllerRef.current.signal,
          });
        } catch (fetchError) {
          if ((fetchError as Error).name === 'AbortError') {
            return;
          }
          throw fetchError;
        }

        if (!response.ok) {
          const errorText = await response.text();
          throw new Error(`HTTP ${response.status}: ${errorText}`);
        }

        // SSE 解析器
        const decoder = new TextDecoder();
        let buffer = '';
        let currentEvent = '';

        const processChunk = (chunk: string) => {
          const lines = (buffer + chunk).split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            // 处理 SSE event 行
            if (line.startsWith('event:')) {
              currentEvent = line.slice(6).trim();
              continue;
            }

            // 空行表示事件结束，重置 event
            if (line.trim() === '') {
              currentEvent = '';
              continue;
            }

            if (line.startsWith('data:')) {
              const data = line.slice(5).trim();
              if (!data) continue;

              // 跳过 error 事件
              if (currentEvent === 'error') {
                try {
                  const parsed = JSON.parse(data);
                  handleSSEError(new Error(parsed.message || 'Server error'));
                } catch {
                  handleSSEError(new Error(data));
                }
                currentEvent = '';
                continue;
              }

              try {
                const parsed = JSON.parse(data) as ChatCompletionChunk;
                handleSSEMessage(parsed);
              } catch {
                // 忽略解析错误
              }
              currentEvent = '';
            }
          }
        };

        const reader = response.body?.getReader();

        if (!reader) {
          // 没有 ReadableStream，用 text() 兜底读取
          const text = await response.text();
          processChunk(text);
          setStreaming(sessionId, false);
          setIsConnecting(false);
          return;
        }

        while (reader) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          const chunk = decoder.decode(value, { stream: true });
          processChunk(chunk);
        }

        setStreaming(sessionId, false);
        setIsConnecting(false);
      } catch (error) {
        setStreaming(sessionId, false);
        setIsConnecting(false);
        handleSSEError(error as Error);
      }
    },
    [
      sessionId,
      isOnline,
      accessToken,
      tenant,
      user,
      addMessage,
      setStreaming,
      clearStreamContent,
      clearSteps,
      addToOfflineQueue,
      handleSSEMessage,
      handleSSEError,
    ]
  );

  // 取消请求（中止正在进行的 SSE 流）
  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setStreaming(sessionId, false);
    clearStreamContent(sessionId);
    clearSteps(sessionId);
    setCurrentRunId(sessionId, null);
    setIsConnecting(false);
  }, [sessionId, setStreaming, clearStreamContent, clearSteps, setCurrentRunId]);

  // 重试
  const retry = useCallback(() => {
    if (lastRequestRef.current) {
      sendMessage(lastRequestRef.current);
    }
  }, [sendMessage]);

  // 清空消息
  const clearMessages = useCallback(() => {
    clearStoreMessages(sessionId);
  }, [clearStoreMessages, sessionId]);

  // 离线消息列表
  const pendingMessages = sessionState.messages.filter((m) => m.is_offline);

  const computedStreaming = sessionState.isStreaming || isConnecting;

  return {
    messages: sessionState.messages,
    isStreaming: computedStreaming,
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