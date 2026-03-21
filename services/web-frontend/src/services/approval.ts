import api from '@/services/api';
import type {
  ApprovalTask,
  ApprovalActionRequest,
} from '@/types/approval';

export interface ApprovalListParams {
  page?: number;
  page_size?: number;
  status?: string;
  priority?: string;
  task_type?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

export interface ApprovalListResponse {
  items: ApprovalTask[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

/**
 * 获取审批列表
 */
export async function getApprovals(params: ApprovalListParams = {}): Promise<ApprovalListResponse> {
  const response = await api.get<ApprovalListResponse>('/approvals', { params });
  return response.data;
}

/**
 * 获取审批详情
 */
export async function getApproval(id: string): Promise<ApprovalTask> {
  const response = await api.get<ApprovalTask>(`/approvals/${id}`);
  return response.data;
}

/**
 * 通过审批
 */
export async function approveApproval(
  id: string,
  data: ApprovalActionRequest = {}
): Promise<ApprovalTask> {
  const response = await api.post<ApprovalTask>(`/approvals/${id}/approve`, data);
  return response.data;
}

/**
 * 拒绝审批
 */
export async function rejectApproval(
  id: string,
  data: ApprovalActionRequest = {}
): Promise<ApprovalTask> {
  const response = await api.post<ApprovalTask>(`/approvals/${id}/reject`, data);
  return response.data;
}
