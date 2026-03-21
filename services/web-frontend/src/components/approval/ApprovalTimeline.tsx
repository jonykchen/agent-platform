import { Timeline, Typography, Tag, Empty } from 'antd';
import {
  Clock,
  User,
  CheckCircle,
  XCircle,
  Timer,
  FileText,
  AlertCircle,
} from 'lucide-react';
import type { ApprovalTask, ApprovalStatus } from '@/types/approval';
import { formatDateTime, formatRelativeTime } from '@/utils/date';

const { Text, Paragraph } = Typography;

interface ApprovalTimelineProps {
  approval: ApprovalTask;
}

interface TimelineItem {
  status: ApprovalStatus | 'created';
  title: string;
  description?: string;
  time: string;
  actor?: string;
  icon: React.ReactNode;
  color: string;
}

const statusTimelineConfig: Record<ApprovalStatus | 'created', { icon: React.ReactNode; color: string }> = {
  created: { icon: <FileText className="w-4 h-4" />, color: 'blue' },
  pending: { icon: <Clock className="w-4 h-4" />, color: 'orange' },
  approved: { icon: <CheckCircle className="w-4 h-4" />, color: 'green' },
  rejected: { icon: <XCircle className="w-4 h-4" />, color: 'red' },
  expired: { icon: <Timer className="w-4 h-4" />, color: 'gray' },
  cancelled: { icon: <AlertCircle className="w-4 h-4" />, color: 'gray' },
};

export function ApprovalTimeline({ approval }: ApprovalTimelineProps) {
  const items: TimelineItem[] = [];

  // 1. 创建事件
  items.push({
    status: 'created',
    title: '审批任务创建',
    description: approval.description,
    time: approval.created_at,
    actor: approval.requester_id,
    icon: statusTimelineConfig.created.icon,
    color: statusTimelineConfig.created.color,
  });

  // 2. 分配事件（如果有）
  if (approval.assignee_id) {
    items.push({
      status: 'pending',
      title: '分配审批人',
      description: `审批任务已分配给 ${approval.assignee_id}`,
      time: approval.updated_at,
      actor: approval.assignee_id,
      icon: <User className="w-4 h-4" />,
      color: 'blue',
    });
  }

  // 3. 审批结果
  if (approval.status !== 'pending') {
    const config = statusTimelineConfig[approval.status];
    let title = '';
    let description = '';

    switch (approval.status) {
      case 'approved':
        title = '审批通过';
        description = approval.review_comment || '审批人已同意此请求';
        break;
      case 'rejected':
        title = '审批拒绝';
        description = approval.review_comment || '审批人已拒绝此请求';
        break;
      case 'expired':
        title = '审批过期';
        description = '审批任务已超过有效期';
        break;
      case 'cancelled':
        title = '审批取消';
        description = '审批任务已被取消';
        break;
    }

    items.push({
      status: approval.status,
      title,
      description,
      time: approval.reviewed_at || approval.updated_at,
      actor: approval.reviewer_id,
      icon: config.icon,
      color: config.color,
    });
  }

  if (items.length === 0) {
    return <Empty description="暂无审批记录" />;
  }

  return (
    <div className="approval-timeline">
      <Timeline
        items={items.map((item) => ({
          color: item.color,
          dot: <span className="flex items-center justify-center">{item.icon}</span>,
          children: (
            <div className="pb-4">
              <div className="flex items-center gap-2 mb-1">
                <Text strong>{item.title}</Text>
                {item.status !== 'created' && item.status !== 'pending' && (
                  <Tag color={item.color} className="text-xs">
                    {item.status}
                  </Tag>
                )}
              </div>
              {item.description && (
                <Paragraph className="!mb-1 text-sm text-gray-600">
                  {item.description}
                </Paragraph>
              )}
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatDateTime(item.time)}
                </span>
                {item.actor && (
                  <span className="flex items-center gap-1">
                    <User className="w-3 h-3" />
                    {item.actor}
                  </span>
                )}
              </div>
            </div>
          ),
        }))}
      />

      {/* 过期时间提示 */}
      {approval.status === 'pending' && approval.expires_at && (
        <div className="mt-4 p-3 bg-orange-50 rounded-lg border border-orange-100">
          <div className="flex items-center gap-2 text-orange-600">
            <Timer className="w-4 h-4" />
            <Text className="text-orange-600">
              此审批将于 {formatDateTime(approval.expires_at)} 过期
            </Text>
          </div>
          <Text type="secondary" className="text-xs">
            ({formatRelativeTime(approval.expires_at)} 后过期)
          </Text>
        </div>
      )}
    </div>
  );
}

export default ApprovalTimeline;
