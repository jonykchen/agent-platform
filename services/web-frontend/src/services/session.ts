import api from './api';
import type { Session } from '@/types/chat';
import type { PageResponse } from '@/types/common';

export interface CreateSessionRequest {
  session_type?: 'chat' | 'task' | 'workflow';
  title?: string;
}

export interface SessionListParams {
  status?: 'active' | 'archived' | 'closed';
  page?: number;
  pageSize?: number;
  search?: string;
}

export interface SessionDetail extends Session {
  messages_count: number;
  last_message?: string;
  last_message_at?: string;
}

export const sessionService = {
  /** 获取会话列表 */
  async list(params?: SessionListParams): Promise<PageResponse<SessionDetail>> {
    const { data } = await api.get('/sessions', { params });
    return data;
  },

  /** 获取单个会话 */
  async get(sessionId: string): Promise<SessionDetail> {
    const { data } = await api.get(`/sessions/${sessionId}`);
    return data;
  },

  /** 创建会话 */
  async create(request?: CreateSessionRequest): Promise<Session> {
    const { data } = await api.post('/sessions', request);
    return data;
  },

  /** 删除会话 */
  async delete(sessionId: string): Promise<void> {
    await api.delete(`/sessions/${sessionId}`);
  },

  /** 归档会话 */
  async archive(sessionId: string): Promise<Session> {
    const { data } = await api.post(`/sessions/${sessionId}/archive`);
    return data;
  },

  /** 恢复会话 */
  async unarchive(sessionId: string): Promise<Session> {
    const { data } = await api.post(`/sessions/${sessionId}/unarchive`);
    return data;
  },

  /** 更新会话标题 */
  async updateTitle(sessionId: string, title: string): Promise<Session> {
    const { data } = await api.patch(`/sessions/${sessionId}`, { title });
    return data;
  },
};

export default sessionService;
