import api from './api';
import type { ToolDefinition, ToolRegisterRequest, ToolInvocation } from '@/types/tools';
import type { PageResponse, PageRequest } from '@/types/common';

/** 工具列表查询参数 */
export interface GetToolsParams extends Partial<PageRequest> {
  search?: string;
  category?: 'query' | 'write' | 'external';
  risk_level?: 'low' | 'medium' | 'high' | 'critical';
  status?: 'draft' | 'active' | 'disabled' | 'deprecated' | 'sunset';
  enabled?: boolean;
}

/** 工具调用历史查询参数 */
export interface GetToolInvocationsParams extends Partial<PageRequest> {
  tool_name: string;
  status?: 'pending' | 'success' | 'failed' | 'rejected' | 'timeout';
  start_date?: string;
  end_date?: string;
}

/**
 * 获取工具列表
 */
export async function getTools(params?: GetToolsParams): Promise<PageResponse<ToolDefinition>> {
  const response = await api.get<PageResponse<ToolDefinition>>('/internal/tools', { params });
  return response.data;
}

/**
 * 获取工具详情
 */
export async function getTool(name: string): Promise<ToolDefinition> {
  const response = await api.get<ToolDefinition>(`/internal/tools/${encodeURIComponent(name)}`);
  return response.data;
}

/**
 * 注册工具
 */
export async function registerTool(request: ToolRegisterRequest): Promise<ToolDefinition> {
  const response = await api.post<ToolDefinition>('/internal/tools/register', request);
  return response.data;
}

/**
 * 启用工具
 */
export async function enableTool(name: string): Promise<ToolDefinition> {
  const response = await api.post<ToolDefinition>(`/internal/tools/${encodeURIComponent(name)}/enable`);
  return response.data;
}

/**
 * 禁用工具
 */
export async function disableTool(name: string): Promise<ToolDefinition> {
  const response = await api.post<ToolDefinition>(`/internal/tools/${encodeURIComponent(name)}/disable`);
  return response.data;
}

/**
 * 获取工具调用历史
 */
export async function getToolInvocations(
  params: GetToolInvocationsParams
): Promise<PageResponse<ToolInvocation>> {
  const { tool_name, ...queryParams } = params;
  const response = await api.get<PageResponse<ToolInvocation>>(
    `/internal/tools/${encodeURIComponent(tool_name)}/invocations`,
    { params: queryParams }
  );
  return response.data;
}
