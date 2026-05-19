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

/** 审计查询参数（请求参数使用 camelCase） */
export interface AuditQueryParams {
  pageNumber: number;
  pageSize: number;
  eventType?: string;
  eventCategory?: string;
  severity?: string;
  userId?: string;
  resourceType?: string;
  resourceId?: string;
  startTime?: string;
  endTime?: string;
  sortBy?: string;
  sortDescending?: boolean;
}