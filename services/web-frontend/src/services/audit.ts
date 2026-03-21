import api from './api';
import type { AuditEvent, AuditQueryParams } from '@/types/audit';
import type { PageResponse } from '@/types/common';

/**
 * 获取审计事件列表
 */
export async function getAuditEvents(params: AuditQueryParams): Promise<PageResponse<AuditEvent>> {
  const response = await api.get<PageResponse<AuditEvent>>('/audit/events', { params });
  return response.data;
}

/**
 * 获取单个审计事件详情
 */
export async function getAuditEvent(eventId: string): Promise<AuditEvent> {
  const response = await api.get<AuditEvent>(`/audit/events/${eventId}`);
  return response.data;
}

/**
 * 导出审计数据
 */
export async function exportAuditEvents(
  params: Omit<AuditQueryParams, 'page_number' | 'page_size'> & { format?: 'csv' | 'json' },
  format: 'csv' | 'json' = 'json'
): Promise<Blob> {
  const response = await api.get('/audit/events/export', {
    params: { ...params, format },
    responseType: 'blob',
  });
  return response.data;
}

/**
 * 获取审计事件类型列表
 */
export async function getAuditEventTypes(): Promise<string[]> {
  const response = await api.get<string[]>('/audit/events/types');
  return response.data;
}

/**
 * 获取审计统计信息
 */
export async function getAuditStats(params: { start_time: string; end_time: string }): Promise<{
  total_events: number;
  by_severity: Record<string, number>;
  by_category: Record<string, number>;
  by_event_type: Record<string, number>;
}> {
  const response = await api.get('/audit/stats', { params });
  return response.data;
}
