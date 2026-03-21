/** 租户配置 */
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

/** 租户设置 */
export interface TenantSettings {
  max_sessions_per_user: number;
  max_tokens_per_day: number;
  max_concurrent_runs: number;
  allowed_models: string[];
  default_model: string;
  enable_knowledge_base: boolean;
  enable_multi_agent: boolean;
  data_retention_days: number;
}

/** 租户配额 */
export interface TenantQuotas {
  daily_tokens: number;
  monthly_cost_usd: number;
}