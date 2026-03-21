import api from './api';
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

export const tenantService = {
  /** 获取租户配置 */
  async getConfig(tenantId: string): Promise<TenantConfig> {
    const { data } = await api.get(`/tenants/${tenantId}`);
    return data;
  },

  /** 更新设置 */
  async updateSettings(tenantId: string, settings: Partial<TenantSettings>): Promise<void> {
    await api.patch(`/tenants/${tenantId}/settings`, settings);
  },

  /** 获取配额使用情况 */
  async getQuotaUsage(tenantId: string): Promise<QuotaUsage> {
    const { data } = await api.get(`/tenants/${tenantId}/quota`);
    return data;
  },

  /** 重置为默认配置 */
  async resetSettings(tenantId: string): Promise<void> {
    await api.post(`/tenants/${tenantId}/settings/reset`);
  },

  /** 获取租户用量统计 */
  async getUsage(): Promise<{
    daily_tokens_used: number;
    monthly_tokens_used: number;
    daily_cost_usd: number;
    monthly_cost_usd: number;
    active_sessions: number;
    active_runs: number;
    storage_used_mb: number;
  }> {
    const { data } = await api.get('/tenant/usage');
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
    const { data } = await api.get('/tenant/models');
    return data;
  },
};

export default tenantService;