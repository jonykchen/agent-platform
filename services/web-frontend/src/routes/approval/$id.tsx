import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  Button,
  Typography,
  Descriptions,
  Tag,
  Space,
  Divider,
  Modal,
  Input,
  message,
  Alert,
  Skeleton,
  Tooltip,
} from 'antd';
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  Clock,
  User,
  AlertCircle,
  Copy,
  ExternalLink,
} from 'lucide-react';
import { useState, useCallback } from 'react';
import { getApproval, approveApproval, rejectApproval } from '@/services/approval';
import type { ApprovalTask, ApprovalStatus, ApprovalType } from '@/types/approval';
import { ApprovalTimeline } from '@/components/approval/ApprovalTimeline';
import { LoadingState } from '@/components/feedback/LoadingState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { formatDateTime } from '@/utils/date';

const { Title, Text, Paragraph } = Typography;

// 状态配置
const statusConfig: Record<ApprovalStatus, { color: string; text: string; icon: React.ReactNode }> = {
  pending: { color: 'orange', text: '待审批', icon: <Clock className="w-5 h-5" /> },
  approved: { color: 'green', text: '已通过', icon: <CheckCircle className="w-5 h-5" /> },
  rejected: { color: 'red', text: '已拒绝', icon: <XCircle className="w-5 h-5" /> },
  expired: { color: 'default', text: '已过期', icon: <AlertCircle className="w-5 h-5" /> },
  cancelled: { color: 'default', text: '已取消', icon: <XCircle className="w-5 h-5" /> },
};

// 优先级配置
const priorityConfig: Record<string, { color: string; text: string }> = {
  low: { color: 'default', text: '低' },
  normal: { color: 'blue', text: '普通' },
  high: { color: 'orange', text: '高' },
  urgent: { color: 'red', text: '紧急' },
};

// 类型配置
const typeConfig: Record<ApprovalType, { color: string; text: string }> = {
  tool_approval: { color: 'purple', text: '工具审批' },
  sensitive_action: { color: 'magenta', text: '敏感操作' },
  high_value_transaction: { color: 'gold', text: '高价值交易' },
};

export const Route = createFileRoute('/approval/$id')({
  component: ApprovalDetailPage,
  beforeLoad: async ({ params }) => {
    // 权限检查可在此处添加
    return { approvalId: params.id };
  },
});

function ApprovalDetailPage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();

  // 权限
  const canApprove = hasPermission(Permissions.APPROVAL_APPROVE);
  const canReject = hasPermission(Permissions.APPROVAL_REJECT);

  // 操作 Modal
  const [actionModal, setActionModal] = useState<{
    visible: boolean;
    type: 'approve' | 'reject';
  }>({
    visible: false,
    type: 'approve',
  });
  const [comment, setComment] = useState('');

  // 获取审批详情
  const {
    data: approval,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['approval', id],
    queryFn: () => getApproval(id),
    staleTime: 30000,
  });

  // 通过审批 mutation
  const approveMutation = useMutation({
    mutationFn: () => approveApproval(id, { comment }),
    onSuccess: () => {
      message.success('审批已通过');
      queryClient.invalidateQueries({ queryKey: ['approval', id] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setActionModal({ visible: false, type: 'approve' });
      setComment('');
    },
    onError: () => {
      message.error('操作失败，请重试');
    },
  });

  // 拒绝审批 mutation
  const rejectMutation = useMutation({
    mutationFn: () => rejectApproval(id, { comment }),
    onSuccess: () => {
      message.warning('审批已拒绝');
      queryClient.invalidateQueries({ queryKey: ['approval', id] });
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setActionModal({ visible: false, type: 'reject' });
      setComment('');
    },
    onError: () => {
      message.error('操作失败，请重试');
    },
  });

  // 返回列表
  const handleBack = useCallback(() => {
    navigate({ to: '/approval' });
  }, [navigate]);

  // 复制 JSON
  const handleCopyJSON = useCallback((obj: Record<string, unknown>) => {
    navigator.clipboard.writeText(JSON.stringify(obj, null, 2));
    message.success('已复制到剪贴板');
  }, []);

  // 打开关联页面
  const handleOpenRelated = useCallback((runId: string) => {
    window.open(`/chat?runId=${runId}`, '_blank');
  }, []);

  // 确认操作
  const confirmAction = useCallback(() => {
    if (actionModal.type === 'approve') {
      approveMutation.mutate();
    } else {
      rejectMutation.mutate();
    }
  }, [actionModal.type, approveMutation, rejectMutation]);

  // Loading 状态
  if (isLoading) {
    return (
      <div className="p-6">
        <Card>
          <Skeleton active paragraph={{ rows: 10 }} />
        </Card>
      </div>
    );
  }

  // Error 状态
  if (error || !approval) {
    return (
      <div className="p-6">
        <Card>
          <EmptyState
            description="审批任务不存在或已被删除"
            action={{
              label: '返回列表',
              onClick: handleBack,
            }}
          />
        </Card>
      </div>
    );
  }

  const status = statusConfig[approval.status];
  const priority = priorityConfig[approval.priority] || priorityConfig.normal;
  const type = typeConfig[approval.task_type];
  const isPending = approval.status === 'pending';
  const isExpired = isPending && new Date(approval.expires_at) < new Date();

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <Button
          type="text"
          icon={<ArrowLeft className="w-4 h-4" />}
          onClick={handleBack}
          className="mb-2"
        >
          返回列表
        </Button>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Title level={4} className="!mb-0">
              {approval.title}
            </Title>
            <Tag color={status.color} className="flex items-center gap-1">
              {status.icon}
              {status.text}
            </Tag>
          </div>
          {isPending && !isExpired && (
            <Space>
              <Button
                danger
                icon={<XCircle className="w-4 h-4" />}
                onClick={() => setActionModal({ visible: true, type: 'reject' })}
                disabled={!canReject}
              >
                拒绝
              </Button>
              <Button
                type="primary"
                icon={<CheckCircle className="w-4 h-4" />}
                onClick={() => setActionModal({ visible: true, type: 'approve' })}
                disabled={!canApprove}
              >
                通过
              </Button>
            </Space>
          )}
        </div>
      </div>

      {/* 过期警告 */}
      {isExpired && (
        <Alert
          message="此审批已过期"
          description="该审批任务已超过有效期，无法再进行操作"
          type="warning"
          showIcon
          className="mb-4"
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：详情 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 基本信息 */}
          <Card title="基本信息">
            <Descriptions column={{ xs: 1, sm: 2 }} bordered size="small">
              <Descriptions.Item label="审批ID">{approval.id}</Descriptions.Item>
              <Descriptions.Item label="类型">
                <Tag color={type.color}>{type.text}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="优先级">
                <Tag color={priority.color}>{priority.text}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={status.color}>{status.text}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="请求人">
                <span className="flex items-center gap-1">
                  <User className="w-4 h-4" />
                  {approval.requester_id}
                </span>
              </Descriptions.Item>
              <Descriptions.Item label="审批人">
                {approval.assignee_id || approval.reviewer_id || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {formatDateTime(approval.created_at)}
              </Descriptions.Item>
              <Descriptions.Item label="过期时间">
                <span className={isExpired ? 'text-red-500' : ''}>
                  {formatDateTime(approval.expires_at)}
                </span>
              </Descriptions.Item>
              {approval.run_id && (
                <Descriptions.Item label="关联会话">
                  <Button
                    type="link"
                    size="small"
                    icon={<ExternalLink className="w-3 h-3" />}
                    onClick={() => handleOpenRelated(approval.run_id)}
                    className="!p-0"
                  >
                    {approval.run_id}
                  </Button>
                </Descriptions.Item>
              )}
              {approval.tool_invocation_id && (
                <Descriptions.Item label="工具调用ID">
                  {approval.tool_invocation_id}
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* 描述 */}
            <div className="mt-4">
              <Text type="secondary" className="block mb-1">描述</Text>
              <Paragraph className="!mb-0">{approval.description}</Paragraph>
            </div>
          </Card>

          {/* 请求上下文 */}
          <Card
            title="请求上下文"
            extra={
              <Tooltip title="复制 JSON">
                <Button
                  type="text"
                  size="small"
                  icon={<Copy className="w-4 h-4" />}
                  onClick={() => handleCopyJSON(approval.request_context)}
                />
              </Tooltip>
            }
          >
            <pre className="bg-gray-50 p-4 rounded overflow-auto text-sm max-h-96">
              {JSON.stringify(approval.request_context, null, 2)}
            </pre>
          </Card>

          {/* 审批结果 */}
          {approval.status !== 'pending' && approval.reviewer_id && (
            <Card title="审批结果">
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="审批人">{approval.reviewer_id}</Descriptions.Item>
                <Descriptions.Item label="审批时间">
                  {formatDateTime(approval.reviewed_at || '')}
                </Descriptions.Item>
                <Descriptions.Item label="审批结果">
                  <Tag color={status.color}>{status.text}</Tag>
                </Descriptions.Item>
                {approval.review_comment && (
                  <Descriptions.Item label="审批意见">
                    {approval.review_comment}
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          )}
        </div>

        {/* 右侧：时间线 */}
        <div>
          <Card title="审批进度">
            <ApprovalTimeline approval={approval} />
          </Card>
        </div>
      </div>

      {/* Action Modal */}
      <Modal
        title={
          actionModal.type === 'approve' ? (
            <span className="flex items-center gap-2">
              <CheckCircle className="w-5 h-5 text-green-500" />
              确认通过审批
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <XCircle className="w-5 h-5 text-red-500" />
              确认拒绝审批
            </span>
          )
        }
        open={actionModal.visible}
        onCancel={() => {
          setActionModal({ visible: false, type: 'approve' });
          setComment('');
        }}
        onOk={confirmAction}
        confirmLoading={approveMutation.isPending || rejectMutation.isPending}
        okText={actionModal.type === 'approve' ? '确认通过' : '确认拒绝'}
        okButtonProps={{ danger: actionModal.type === 'reject' }}
      >
        <div className="py-4">
          <div className="mb-4 p-3 bg-gray-50 rounded">
            <Text strong>{approval.title}</Text>
            <br />
            <Text type="secondary" className="text-sm">
              {approval.description}
            </Text>
          </div>
          <Input.TextArea
            placeholder="请输入审批意见（可选）"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={3}
            maxLength={500}
            showCount
          />
        </div>
      </Modal>
    </div>
  );
}

export default Route;