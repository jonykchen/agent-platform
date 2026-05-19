import api from './api';
import type { Notification } from '@/stores/notificationStore';
import type { PageResponse, PageRequest } from '@/types/common';

/** 通知查询参数（请求参数使用 camelCase） */
export interface NotificationQueryParams extends PageRequest {
  type?: 'approval' | 'system' | 'alert' | 'info';
  read?: boolean;
}

/**
 * 获取通知列表
 */
export async function getNotifications(params: NotificationQueryParams): Promise<PageResponse<Notification>> {
  const response = await api.get<PageResponse<Notification>>('/notifications', { params });
  return response.data;
}

/**
 * 获取未读通知数量
 */
export async function getUnreadCount(): Promise<{ count: number }> {
  const response = await api.get<{ count: number }>('/notifications/unread-count');
  return response.data;
}

/**
 * 标记通知为已读
 */
export async function markAsRead(notificationId: string): Promise<void> {
  await api.patch(`/notifications/${notificationId}/read`);
}

/**
 * 标记所有通知为已读
 */
export async function markAllAsRead(): Promise<void> {
  await api.patch('/notifications/read-all');
}

/**
 * 删除通知
 */
export async function deleteNotification(notificationId: string): Promise<void> {
  await api.delete(`/notifications/${notificationId}`);
}

/**
 * 删除所有已读通知
 */
export async function deleteReadNotifications(): Promise<void> {
  await api.delete('/notifications/read');
}
