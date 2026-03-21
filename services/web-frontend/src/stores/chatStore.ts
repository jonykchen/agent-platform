import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { Message, AgentStepInfo, ChatCompletionChunk } from '@/types/chat';
import { APP_CONFIG } from '@/constants/config';

export interface OfflineMessage {
  id: string;
  sessionId: string;
  content: string;
  createdAt: number;
  retryCount: number;
}

export interface ChatSessionState {
  messages: Message[];
  currentSteps: AgentStepInfo[];
  isStreaming: boolean;
  streamingContent: string;
  currentRunId: string | null;
}

export interface ChatState {
  // 各会话的状态
  sessions: Record<string, ChatSessionState>;

  // 离线消息队列
  offlineQueue: OfflineMessage[];

  // 当前活跃会话 ID
  activeSessionId: string | null;

  // Actions
  setActiveSession: (sessionId: string | null) => void;

  // 消息操作
  setMessages: (sessionId: string, messages: Message[]) => void;
  addMessage: (sessionId: string, message: Message) => void;
  updateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => void;
  clearMessages: (sessionId: string) => void;

  // 流式响应状态
  setStreaming: (sessionId: string, isStreaming: boolean) => void;
  appendStreamContent: (sessionId: string, content: string) => void;
  clearStreamContent: (sessionId: string) => void;
  setCurrentRunId: (sessionId: string, runId: string | null) => void;

  // 步骤信息
  setSteps: (sessionId: string, steps: AgentStepInfo[]) => void;
  addStep: (sessionId: string, step: AgentStepInfo) => void;
  updateStep: (sessionId: string, stepOrder: number, updates: Partial<AgentStepInfo>) => void;
  clearSteps: (sessionId: string) => void;

  // 处理 SSE 响应块
  handleChunk: (sessionId: string, chunk: ChatCompletionChunk) => void;

  // 离线队列操作
  addToOfflineQueue: (message: OfflineMessage) => void;
  removeFromOfflineQueue: (id: string) => void;
  incrementRetryCount: (id: string) => void;
  clearOfflineQueue: () => void;

  // 获取会话状态
  getSessionState: (sessionId: string) => ChatSessionState;

  // 重置会话状态
  resetSessionState: (sessionId: string) => void;
}

const DEFAULT_SESSION_STATE: ChatSessionState = {
  messages: [],
  currentSteps: [],
  isStreaming: false,
  streamingContent: '',
  currentRunId: null,
};

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      sessions: {},
      offlineQueue: [],
      activeSessionId: null,

      setActiveSession: (sessionId) => {
        set({ activeSessionId: sessionId });
      },

      getSessionState: (sessionId) => {
        return get().sessions[sessionId] || DEFAULT_SESSION_STATE;
      },

      setMessages: (sessionId, messages) => {
        set((state) => ({
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              messages,
            },
          },
        }));
      },

      addMessage: (sessionId, message) => {
        set((state) => {
          const sessionState = state.sessions[sessionId] || DEFAULT_SESSION_STATE;
          const existingIds = new Set(sessionState.messages.map((m) => m.id));
          if (existingIds.has(message.id)) {
            return state;
          }
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...sessionState,
                messages: [...sessionState.messages, message],
              },
            },
          };
        });
      },

      updateMessage: (sessionId, messageId, updates) => {
        set((state) => {
          const sessionState = state.sessions[sessionId];
          if (!sessionState) return state;

          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...sessionState,
                messages: sessionState.messages.map((m) =>
                  m.id === messageId ? { ...m, ...updates } : m
                ),
              },
            },
          };
        });
      },

      clearMessages: (sessionId) => {
        set((state) => ({
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              messages: [],
            },
          },
        }));
      },

      setStreaming: (sessionId, isStreaming) => {
        set((state) => ({
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              isStreaming,
            },
          },
        }));
      },

      appendStreamContent: (sessionId, content) => {
        set((state) => {
          const sessionState = state.sessions[sessionId] || DEFAULT_SESSION_STATE;
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...sessionState,
                streamingContent: sessionState.streamingContent + content,
              },
            },
          };
        });
      },

      clearStreamContent: (sessionId) => {
        set((state) => ({
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              streamingContent: '',
            },
          },
        }));
      },

      setCurrentRunId: (sessionId, runId) => {
        set((state) => ({
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              currentRunId: runId,
            },
          },
        }));
      },

      setSteps: (sessionId, steps) => {
        set((state) => ({
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              currentSteps: steps,
            },
          },
        }));
      },

      addStep: (sessionId, step) => {
        set((state) => {
          const sessionState = state.sessions[sessionId] || DEFAULT_SESSION_STATE;
          const existingSteps = sessionState.currentSteps.filter(
            (s) => s.step_order !== step.step_order
          );
          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...sessionState,
                currentSteps: [...existingSteps, step].sort((a, b) => a.step_order - b.step_order),
              },
            },
          };
        });
      },

      updateStep: (sessionId, stepOrder, updates) => {
        set((state) => {
          const sessionState = state.sessions[sessionId];
          if (!sessionState) return state;

          return {
            sessions: {
              ...state.sessions,
              [sessionId]: {
                ...sessionState,
                currentSteps: sessionState.currentSteps.map((s) =>
                  s.step_order === stepOrder ? { ...s, ...updates } : s
                ),
              },
            },
          };
        });
      },

      clearSteps: (sessionId) => {
        set((state) => ({
          sessions: {
            ...state.sessions,
            [sessionId]: {
              ...state.sessions[sessionId],
              currentSteps: [],
            },
          },
        }));
      },

      handleChunk: (sessionId, chunk) => {
        const { addMessage, appendStreamContent, addStep, updateStep, setStreaming, clearStreamContent, setCurrentRunId } = get();

        // 处理步骤信息
        if (chunk.step_info) {
          const step = chunk.step_info;
          if (step.status === 'running' || step.status === 'pending') {
            addStep(sessionId, step);
          } else {
            updateStep(sessionId, step.step_order, step);
          }
        }

        // 处理内容
        if (chunk.delta_content) {
          appendStreamContent(sessionId, chunk.delta_content);
        }

        // 处理完成
        if (chunk.is_final) {
          setStreaming(sessionId, false);
          if (chunk.usage) {
            // 可以记录 token 使用情况
            console.log('Token usage:', chunk.usage);
          }
        }
      },

      addToOfflineQueue: (message) => {
        set((state) => {
          // 限制离线队列大小
          const queue = [...state.offlineQueue, message];
          if (queue.length > APP_CONFIG.MAX_HISTORY_MESSAGES) {
            queue.shift();
          }
          return { offlineQueue: queue };
        });
      },

      removeFromOfflineQueue: (id) => {
        set((state) => ({
          offlineQueue: state.offlineQueue.filter((m) => m.id !== id),
        }));
      },

      incrementRetryCount: (id) => {
        set((state) => ({
          offlineQueue: state.offlineQueue.map((m) =>
            m.id === id ? { ...m, retryCount: m.retryCount + 1 } : m
          ),
        }));
      },

      clearOfflineQueue: () => {
        set({ offlineQueue: [] });
      },

      resetSessionState: (sessionId) => {
        set((state) => {
          const { [sessionId]: _, ...rest } = state.sessions;
          return { sessions: rest };
        });
      },
    }),
    {
      name: 'chat-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        offlineQueue: state.offlineQueue,
      }),
    }
  )
);

export default useChatStore;