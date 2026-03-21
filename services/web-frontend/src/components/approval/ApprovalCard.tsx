import { Card, Tag, Typography, Space, Button } from 'antd';
import {
  Clock,
  User,
  AlertCircle,
  CheckCircle,
  XCircle,
  Timer,
} from 'lucide-react';
import type { ApprovalTask, ApprovalStatus, ApprovalType } from '@/types/approval';
import { formatRelativeTime } from '@/utils/date';
import { useNavigate } from '@tanstack/react-router';

const { Text, Title } = Typography;

interface ApprovalCardProps {
  approval: ApprovalTask;
  onApprove?: (id: string) => void;
  onReject?: (id: string) => void;
  showActions?: boolean;
}

const statusConfig: Record<ApprovalStatus, { color: string; icon: React.ReactNode; text: string }> = {
  pending: { color: 'orange', icon: <Clock className="w-4 h-4" />, text: '待审批' },
  approved: { color: 'green', icon: <CheckCircle className="w-4 h-4" />, text: '已通过' },
  rejected: { color: 'red', icon: <XCircle className="w-4 h-4" />, text: '已拒绝' },
  expired: { color: 'default', icon: <Timer className="w-4 h-4" />, text: '已过期' },
  cancelled: { color: 'default', icon: <XCircle className="w-4 h-4" />, text: '已取消' },
};

const priorityConfig: Record<string, { color: string; text: string }> = {
  low: { color: 'default', text: '低' },
  normal: { color: 'blue', text: '普通' },
  high: { color: 'orange', text: '高' },
  urgent: { color: 'red', text: '紧急' },
};

const typeConfig: Record<ApprovalType, { color: string; text: string }> = {
  tool_approval: { color: 'purple', text: '工具审批' },
  sensitive_action: { color: 'magenta', text: '敏感操作' },
  high_value_transaction: { color: 'gold', text: '高价值交易' },
};

export function ApprovalCard({
  approval,
  onApprove,
  onReject,
  showActions = false,
}: ApprovalCardProps) {
  const navigate = useNavigate();
  const status = statusConfig[approval.status];
  const priority = priorityConfig[approval.priority] || priorityConfig.normal;
  const type = typeConfig[approval.task_type];

  const handleClick = () => {
    navigate({ to: '/approval/$id', params: { id: approval.id } });
  };

  const isPending = approval.status === 'pending';

  return (
    <Card
      hoverable
      className="cursor-pointer transition-shadow hover:shadow-md"
      onClick={handleClick}
    >
      <div className="flex flex-col gap-3">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <Title level={5} className="!mb-1 truncate" title={approval.title}>
              {approval.title}
            </Title>
            <Text type="secondary" className="text-xs">
              ID: {approval.id}
            </Text>
          </div>
          <Tag color={status.color} className="flex items-center gap-1 shrink-0">
            {status.icon}
            {status.text}
          </Tag>
        </div>

        {/* Description */}
        <Text className="text-sm text-gray-600 line-clamp-2" title={approval.description}>
          {approval.description}
        </Text>

        {/* Tags */}
        <Space size={[0, 8]} wrap>
          <Tag color={type.color}>{type.text}</Tag>
          <Tag color={priority.color}>优先级: {priority.text}</Tag>
        </Space>

        {/* Meta Info */}
        <div className="flex items-center justify-between text-xs text-gray-500">
          <Space split={<span className="text-gray-300">|</span>}>
            <span className="flex items-center gap-1">
              <User className="w-3 h-3" />
              {approval.requester_id}
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatRelativeTime(approval.created_at)}
            </span>
          </Space>
          {isPending && approval.expires_at && (
            <span className="flex items-center gap-1 text-orange-500">
              <AlertCircle className="w-3 h-3" />
              {formatRelativeTime(approval.expires_at)} 过期
            </span>
          )}
        </div>

        {/* Review Info */}
        {approval.reviewer_id && (
          <div className="pt-2 border-t border-gray-100 text-xs text-gray-500">
            <Space split={<span className="text-gray-300">|</span>}>
              <span>审批人: {approval.reviewer_id}</span>
              {approval.reviewed_at && (
                <span>审批时间: {formatRelativeTime(approval.reviewed_at)}</span>
              )}
            </Space>
            {approval.review_comment && (
              <div className="mt-1 text-gray-600">
                审批意见: {approval.review_comment}
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        {showActions && isPending && (
          <div className="flex justify-end gap-2 pt-2 border-t border-gray-100">
            <Button
              size="small"
              danger
              onClick={(e) => {
                e.stopPropagation();
                onReject?.(approval.id);
              }}
            >
              拒绝
            </Button>
            <Button
              size="small"
              type="primary"
              onClick={(e) => {
                e.stopPropagation();
                onApprove?.(approval.id);
              }}
            >
              通过
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}

export default ApprovalCard;
