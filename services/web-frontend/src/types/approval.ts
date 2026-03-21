/** 审批任务 */
export interface ApprovalTask {
  id: string;
  run_id: string;
  tool_invocation_id?: string;
  tenant_id: string;
  task_type: ApprovalType;
  title: string;
  description: string;
  request_context: Record<string, unknown>;
  requester_id: string;
  assignee_id?: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  status: ApprovalStatus;
  reviewer_id?: string;
  review_comment?: string;
  reviewed_at?: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export type ApprovalType = 'tool_approval' | 'sensitive_action' | 'high_value_transaction';

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled';

/** 审批操作请求 */
export interface ApprovalActionRequest {
  comment?: string;
}

/** 审批通知（WebSocket 推送） */
export interface ApprovalNotification {
  event_type: 'approval.created' | 'approval.approved' | 'approval.rejected' | 'approval.expired';
  approval_id: string;
  title: string;
  priority: 'low' | 'normal' | 'high' | 'urgent';
  created_at: string;
}