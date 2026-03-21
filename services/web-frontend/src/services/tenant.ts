import api from './api';
import type { TenantConfig, TenantSettings, TenantQuotas } from '@/types/tenant';

/**
 * 获取当前租户配置
 */
export async function getTenantConfig(): Promise<TenantConfig> {
  const response = await api.get<TenantConfig>('/tenant/config');
  return response.data;
}

/**
 * 更新租户设置
 */
export async function updateTenantSettings(settings: Partial<TenantSettings>): Promise<TenantSettings> {
  const response = await api.patch<TenantSettings>('/tenant/settings', settings);
  return response.data;
}

/**
 * 更新租户配额
 */
export async function updateTenantQuotas(quotas: Partial<TenantQuotas>): Promise<TenantQuotas> {
  const response = await api.patch<TenantQuotas>('/tenant/quotas', quotas);
  return response.data;
}

/**
 * 获取租户用量统计
 */
export async function getTenantUsage(): Promise<{
  daily_tokens_used: number;
  monthly_tokens_used: number;
  daily_cost_usd: number;
  monthly_cost_usd: number;
  active_sessions: number;
  active_runs: number;
  storage_used_mb: number;
}> {
  const response = await api.get('/tenant/usage');
  return response.data;
}

/**
 * 获取可用模型列表
 */
export async function getAvailableModels(): Promise<Array<{
  id: string;
  name: string;
  provider: string;
  max_tokens: number;
  cost_per_1k_tokens: number;
}>> {
  const response = await api.get('/tenant/models');
  return response.data;
}
