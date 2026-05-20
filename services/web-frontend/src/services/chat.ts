import api from './api';
import type { Message, AgentRun, AgentStep } from '@/types/chat';
import type { PageResponse } from '@/types/common';

export interface GetMessagesParams {
  page?: number;
  pageSize?: number;
  before?: string; // ISO date
  after?: string; // ISO date
}

export interface MessageDetail extends Message {
  run?: AgentRun;
  steps?: AgentStep[];
}

export const chatService = {
  /** 获取会话的消息列表 */
  async getMessages(sessionId: string, params?: GetMessagesParams): Promise<PageResponse<MessageDetail>> {
    const { data } = await api.get(`/sessions/${sessionId}/messages`, { params });
    return data;
  },

  /** 获取单个消息详情 */
  async getMessage(sessionId: string, messageId: string): Promise<MessageDetail> {
    const { data } = await api.get(`/sessions/${sessionId}/messages/${messageId}`);
    return data;
  },

  /** 获取 Agent Run 详情 */
  async getRun(sessionId: string, runId: string): Promise<AgentRun> {
    const { data } = await api.get(`/sessions/${sessionId}/runs/${runId}`);
    return data;
  },

  /** 获取 Run 的步骤列表 */
  async getRunSteps(sessionId: string, runId: string): Promise<AgentStep[]> {
    const { data } = await api.get(`/sessions/${sessionId}/runs/${runId}/steps`);
    return data;
  },

  /** 取消正在运行的 Agent */
  async cancelRun(sessionId: string, runId: string): Promise<void> {
    await api.post(`/sessions/${sessionId}/runs/${runId}/cancel`);
  },
};

export default chatService;