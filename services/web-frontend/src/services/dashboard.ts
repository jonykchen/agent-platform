import api from './api';

/** 仪表盘统计数据 */
export interface DashboardStats {
  total_sessions: number;
  total_runs: number;
  total_tokens: number;
  total_cost_usd: number;
  success_rate: number;
  avg_response_time_ms: number;
  active_users: number;
  pending_approvals: number;
}

/** 每日运行统计 */
export interface DailyRunStats {
  date: string;
  runs: number;
  successful: number;
  failed: number;
  avg_duration_ms: number;
}

/** 每日成本统计 */
export interface DailyCostStats {
  date: string;
  cost_usd: number;
  tokens: number;
}

/** Token 分布统计 */
export interface TokenDistribution {
  model: string;
  tokens: number;
  percentage: number;
  cost_usd: number;
}

/** 模型调用统计 */
export interface ModelCallStats {
  model: string;
  total_calls: number;
  success_rate: number;
  avg_latency_ms: number;
  total_tokens: number;
  cost_usd: number;
}

/** 时间范围参数 */
export type TimeRange = '24h' | '7d' | '30d' | '90d';

/**
 * 获取仪表盘统计数据
 */
export async function getDashboardStats(range?: TimeRange): Promise<DashboardStats> {
  const response = await api.get<DashboardStats>('/dashboard/stats', {
    params: { range },
  });
  return response.data;
}

/**
 * 获取每日运行趋势
 */
export async function getDailyRunStats(params: {
  start_date: string;
  end_date: string;
}): Promise<DailyRunStats[]> {
  const response = await api.get<DailyRunStats[]>('/dashboard/runs/daily', { params });
  return response.data;
}

/**
 * 获取每日成本趋势
 */
export async function getDailyCostStats(params: {
  start_date: string;
  end_date: string;
}): Promise<DailyCostStats[]> {
  const response = await api.get<DailyCostStats[]>('/dashboard/costs/daily', { params });
  return response.data;
}

/**
 * 获取 Token 分布
 */
export async function getTokenDistribution(params: {
  start_date: string;
  end_date: string;
}): Promise<TokenDistribution[]> {
  const response = await api.get<TokenDistribution[]>('/dashboard/tokens/distribution', { params });
  return response.data;
}

/**
 * 获取模型调用统计
 */
export async function getModelCallStats(params: {
  start_date: string;
  end_date: string;
}): Promise<ModelCallStats[]> {
  const response = await api.get<ModelCallStats[]>('/dashboard/models/stats', { params });
  return response.data;
}

/**
 * 获取实时告警
 */
export async function getActiveAlerts(): Promise<Array<{
  id: string;
  type: 'error' | 'warning' | 'info';
  message: string;
  source: string;
  created_at: string;
}>> {
  const response = await api.get('/dashboard/alerts');
  return response.data;
}
