/** 审计事件 */
export interface AuditEvent {
  id: number;
  event_id: string;
  event_type: string;
  event_category: 'lifecycle' | 'security' | 'business' | 'system';
  severity: 'info' | 'warn' | 'error' | 'critical';
  tenant_id: string;
  user_id: string;
  resource_type?: string;
  resource_id?: string;
  action: string;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  details?: Record<string, unknown>;
  request_id: string;
  trace_id: string;
  ip_address?: string;
  user_agent?: string;
  source_service: string;
  created_at: string;
}

/** 审计查询参数 */
export interface AuditQueryParams {
  page_number: number;
  page_size: number;
  event_type?: string;
  event_category?: string;
  severity?: string;
  user_id?: string;
  resource_type?: string;
  resource_id?: string;
  start_time?: string;
  end_time?: string;
  sort_by?: string;
  sort_descending?: boolean;
}