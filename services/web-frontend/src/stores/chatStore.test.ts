import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore } from './chatStore';
import type { Message, ChatCompletionChunk } from '@/types/chat';

const SID = 'sess_test';

function resetStore() {
  // 重置全部会话与离线队列，避免测试间串扰
  useChatStore.setState({ sessions: {}, offlineQueue: [] });
}

function userMsg(content: string): Message {
  return {
    id: `m_${content}`,
    session_id: SID,
    role: 'user',
    content,
    created_at: new Date().toISOString(),
  };
}

describe('chatStore - 消息管理', () => {
  beforeEach(resetStore);

  it('addMessage 追加消息到会话', () => {
    useChatStore.getState().addMessage(SID, userMsg('你好'));
    const state = useChatStore.getState().getSessionState(SID);
    expect(state.messages).toHaveLength(1);
    expect(state.messages[0].content).toBe('你好');
  });

  it('不同会话相互隔离', () => {
    useChatStore.getState().addMessage(SID, userMsg('A'));
    useChatStore.getState().addMessage('other', userMsg('B'));
    expect(useChatStore.getState().getSessionState(SID).messages).toHaveLength(1);
    expect(useChatStore.getState().getSessionState('other').messages).toHaveLength(1);
  });
});

describe('chatStore - 流式内容', () => {
  beforeEach(resetStore);

  it('appendStreamContent 累积流式片段', () => {
    const { appendStreamContent, getSessionState } = useChatStore.getState();
    appendStreamContent(SID, '你');
    appendStreamContent(SID, '好');
    appendStreamContent(SID, '世界');
    expect(getSessionState(SID).streamingContent).toBe('你好世界');
  });

  it('clearStreamContent 清空流式缓冲', () => {
    const { appendStreamContent, clearStreamContent, getSessionState } = useChatStore.getState();
    appendStreamContent(SID, 'abc');
    clearStreamContent(SID);
    expect(getSessionState(SID).streamingContent).toBe('');
  });
});

describe('chatStore - handleChunk (SSE 块处理)', () => {
  beforeEach(resetStore);

  it('增量块累积内容', () => {
    const chunk: ChatCompletionChunk = {
      delta_content: '部分回答',
      is_final: false,
      finish_reason: null as never,
    };
    useChatStore.getState().handleChunk(SID, chunk);
    expect(useChatStore.getState().getSessionState(SID).streamingContent).toBe('部分回答');
  });

  it('is_final 块停止流式', () => {
    const { handleChunk, setStreaming, getSessionState } = useChatStore.getState();
    setStreaming(SID, true);
    handleChunk(SID, { delta_content: '', is_final: true, finish_reason: 'stop' as never });
    expect(getSessionState(SID).isStreaming).toBe(false);
  });

  it('多个增量块顺序拼接', () => {
    const { handleChunk, getSessionState } = useChatStore.getState();
    handleChunk(SID, { delta_content: '一', is_final: false, finish_reason: null as never });
    handleChunk(SID, { delta_content: '二', is_final: false, finish_reason: null as never });
    handleChunk(SID, { delta_content: '三', is_final: true, finish_reason: 'stop' as never });
    expect(getSessionState(SID).streamingContent).toBe('一二三');
  });
});

describe('chatStore - 离线队列', () => {
  beforeEach(resetStore);

  it('addToOfflineQueue 入队，removeFromOfflineQueue 出队', () => {
    const { addToOfflineQueue, removeFromOfflineQueue } = useChatStore.getState();
    addToOfflineQueue({ id: 'o1', sessionId: SID, content: 'x', createdAt: 1, retryCount: 0 });
    expect(useChatStore.getState().offlineQueue).toHaveLength(1);
    removeFromOfflineQueue('o1');
    expect(useChatStore.getState().offlineQueue).toHaveLength(0);
  });

  it('incrementRetryCount 递增重试次数', () => {
    const { addToOfflineQueue, incrementRetryCount } = useChatStore.getState();
    addToOfflineQueue({ id: 'o2', sessionId: SID, content: 'x', createdAt: 1, retryCount: 0 });
    incrementRetryCount('o2');
    expect(useChatStore.getState().offlineQueue[0].retryCount).toBe(1);
  });
});
