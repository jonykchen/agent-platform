import api from './api';
import { useAuthStore } from '@/stores/authStore';
import type { Tenant, TenantSettings, TenantQuotas } from '@/types/tenant';

export interface TenantConfig {
  id: string;
  name: string;
  tier: 'free' | 'standard' | 'premium' | 'enterprise';
  features: string[];
  settings: TenantSettings;
  quotas: TenantQuotas;
  created_at: string;
  updated_at: string;
}

export interface QuotaUsage {
  daily_tokens_used: number;
  daily_tokens_limit: number;
  monthly_cost_used: number;
  monthly_cost_limit: number;
  concurrent_runs_current: number;
  concurrent_runs_limit: number;
}

/** 获取当前租户ID */
function getCurrentTenantId(): string {
  const tenant = useAuthStore.getState().tenant;
  if (!tenant?.id) {
    throw new Error('No tenant found in auth store');
  }
  return tenant.id;
}

export const tenantService = {
  /** 获取租户配置 */
  async getConfig(tenantId?: string): Promise<TenantConfig> {
    const id = tenantId || getCurrentTenantId();
    const { data } = await api.get(`/tenants/${id}`);
    return data;
  },

  /** 更新设置 */
  async updateSettings(tenantId: string, settings: Partial<TenantSettings>): Promise<void> {
    await api.patch(`/tenants/${tenantId}/settings`, settings);
  },

  /** 获取配额使用情况 */
  async getQuotaUsage(tenantId?: string): Promise<QuotaUsage> {
    const id = tenantId || getCurrentTenantId();
    const { data } = await api.get(`/tenants/${id}/quota`);
    return data;
  },

  /** 重置为默认配置 */
  async resetSettings(tenantId?: string): Promise<void> {
    const id = tenantId || getCurrentTenantId();
    await api.post(`/tenants/${id}/settings/reset`);
  },

  /** 获取租户用量统计 */
  async getUsage(tenantId?: string): Promise<{
    daily_tokens_used: number;
    monthly_tokens_used: number;
    daily_cost_usd: number;
    monthly_cost_usd: number;
    active_sessions: number;
    active_runs: number;
    storage_used_mb: number;
  }> {
    const id = tenantId || getCurrentTenantId();
    const { data } = await api.get(`/tenants/${id}/usage`);
    return data;
  },

  /** 获取可用模型列表 */
  async getAvailableModels(): Promise<Array<{
    id: string;
    name: string;
    provider: string;
    max_tokens: number;
    cost_per_1k_tokens: number;
  }>> {
    const { data } = await api.get('/tenants/models');
    return data;
  },
};

export default tenantService;