/** 通用 Header（所有请求必须携带） */
export interface RequestHeader {
  'X-Request-ID': string;
  'X-Tenant-ID': string;
  'X-User-ID': string;
  'X-Trace-ID': string;
}

/** 分页请求 */
export interface PageRequest {
  page_number: number;
  page_size: number;
  sort_by?: string;
  sort_descending?: boolean;
}

/** 分页响应 */
export interface PageResponse<T> {
  items: T[];
  total_count: number;
  page_number: number;
  total_pages: number;
  has_next: boolean;
}

/** API 统一响应 */
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: import('./error').ErrorDetail;
  request_id: string;
  timestamp_ms: number;
}