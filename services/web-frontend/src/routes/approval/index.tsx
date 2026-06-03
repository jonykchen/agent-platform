import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import {
  Table,
  Card,
  Button,
  Input,
  Select,
  Space,
  Tag,
  Typography,
  Modal,
  message,
  Tooltip,
  Badge,
} from 'antd';
import {
  Search,
  RefreshCw,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { useState, useMemo, useCallback } from 'react';
import { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { FilterValue, SorterResult } from 'antd/es/table/interface';
import { getApprovals, approveApproval, rejectApproval } from '@/services/approval';
import type { ApprovalTask, ApprovalStatus, ApprovalType } from '@/types/approval';
import type { ApprovalNotification } from '@/types/approval';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageLayout } from '@/components/layout/PageLayout';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useNotificationStore } from '@/stores/notificationStore';
import { APP_CONFIG } from '@/constants/config';
import { formatDateTime, formatRelativeTime } from '@/utils/date';
import { ROUTE_PATHS } from '@/constants/routes';
import { generateRequestId } from '@/utils/request';

const { Title, Text } = Typography;

export const Route = createFileRoute('/approval/')({
  component: ApprovalListPage,
});

// 状态配置
const statusConfig: Record<ApprovalStatus, { color: string; text: string }> = {
  pending: { color: 'orange', text: '待审批' },
  approved: { color: 'green', text: '已通过' },
  rejected: { color: 'red', text: '已拒绝' },
  expired: { color: 'default', text: '已过期' },
  cancelled: { color: 'default', text: '已取消' },
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

function ApprovalListPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  const addNotification = useNotificationStore((state) => state.addNotification);

  // 权限
  const canApprove = hasPermission(Permissions.APPROVAL_APPROVE);
  const canReject = hasPermission(Permissions.APPROVAL_REJECT);

  // 筛选状态
  const [filters, setFilters] = useState<{
    page: number;
    pageSize: number;
    status?: string;
    priority?: string;
    taskType?: string;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
    search?: string;
  }>({
    page: 1,
    pageSize: APP_CONFIG.DEFAULT_PAGE_SIZE,
  });

  // 搜索关键词
  const [searchText, setSearchText] = useState('');

  // 审批操作 Modal
  const [actionModal, setActionModal] = useState<{
    visible: boolean;
    type: 'approve' | 'reject';
    approval: ApprovalTask | null;
  }>({
    visible: false,
    type: 'approve',
    approval: null,
  });
  const [comment, setComment] = useState('');

  // 获取审批列表
  const {
    data,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['approvals', filters],
    queryFn: () => getApprovals(filters),
    staleTime: 30000,
  });

  // WebSocket 连接接收实时通知
  const wsUrl = `${import.meta.env.VITE_WS_URL || '/ws'}/notifications`;
  useWebSocket<ApprovalNotification>({
    url: wsUrl,
    onMessage: (notification) => {
      // 添加通知
      addNotification({
        id: generateRequestId(),
        type: 'approval',
        title: notification.title,
        message: `新审批任务: ${notification.title}`,
        read: false,
        priority: notification.priority,
        actionUrl: ROUTE_PATHS.approvalDetail(notification.approval_id),
        createdAt: notification.created_at,
      });

      // 刷新列表
      queryClient.invalidateQueries({ queryKey: ['approvals'] });

      // 显示消息
      message.info(`收到新审批任务: ${notification.title}`);
    },
  });

  // 通过审批 mutation
  const approveMutation = useMutation({
    mutationFn: (id: string) => approveApproval(id, { comment }),
    onSuccess: () => {
      message.success('审批已通过');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setActionModal({ visible: false, type: 'approve', approval: null });
      setComment('');
    },
    onError: () => {
      message.error('操作失败，请重试');
    },
  });

  // 拒绝审批 mutation
  const rejectMutation = useMutation({
    mutationFn: (id: string) => rejectApproval(id, { comment }),
    onSuccess: () => {
      message.warning('审批已拒绝');
      queryClient.invalidateQueries({ queryKey: ['approvals'] });
      setActionModal({ visible: false, type: 'reject', approval: null });
      setComment('');
    },
    onError: () => {
      message.error('操作失败，请重试');
    },
  });

  // 处理审批操作
  const handleAction = useCallback((approval: ApprovalTask, type: 'approve' | 'reject') => {
    setActionModal({
      visible: true,
      type,
      approval,
    });
    setComment('');
  }, []);

  // 确认审批操作
  const confirmAction = useCallback(() => {
    if (!actionModal.approval) return;

    if (actionModal.type === 'approve') {
      approveMutation.mutate(actionModal.approval.id);
    } else {
      rejectMutation.mutate(actionModal.approval.id);
    }
  }, [actionModal, approveMutation, rejectMutation]);

  // 表格列配置
  const columns: ColumnsType<ApprovalTask> = useMemo(() => [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string, record) => (
        <a
          href={`/approval/${record.id}`}
          onClick={(e) => {
            e.preventDefault();
            window.location.href = `/approval/${record.id}`;
          }}
        >
          {text}
        </a>
      ),
    },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      width: 120,
      render: (type: ApprovalType) => {
        const config = typeConfig[type];
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      render: (priority: string) => {
        const config = priorityConfig[priority] || priorityConfig.normal;
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: ApprovalStatus) => {
        const config = statusConfig[status];
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '请求人',
      dataIndex: 'requester_id',
      key: 'requester_id',
      width: 120,
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      sorter: true,
      render: (time: string) => (
        <Tooltip title={formatDateTime(time)}>
          <span>{formatRelativeTime(time)}</span>
        </Tooltip>
      ),
    },
    {
      title: '过期时间',
      dataIndex: 'expires_at',
      key: 'expires_at',
      width: 160,
      render: (time: string, record) => {
        if (record.status !== 'pending') return '-';
        const isExpired = new Date(time) < new Date();
        return (
          <Tooltip title={formatDateTime(time)}>
            <span className={isExpired ? 'text-red-500' : 'text-gray-500'}>
              {isExpired ? '已过期' : formatRelativeTime(time)}
            </span>
          </Tooltip>
        );
      },
    },
    {
      title: '操作',
      key: 'actions',
      width: 150,
      render: (_, record) => {
        if (record.status !== 'pending') return '-';
        return (
          <Space size="small">
            <Tooltip title="通过">
              <Button
                type="primary"
                size="small"
                icon={<CheckCircle className="w-4 h-4" />}
                disabled={!canApprove}
                onClick={() => handleAction(record, 'approve')}
              />
            </Tooltip>
            <Tooltip title="拒绝">
              <Button
                danger
                size="small"
                icon={<XCircle className="w-4 h-4" />}
                disabled={!canReject}
                onClick={() => handleAction(record, 'reject')}
              />
            </Tooltip>
          </Space>
        );
      },
    },
  ], [canApprove, canReject, handleAction]);

  // 表格分页和排序变化
  const handleTableChange = useCallback((
    pagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>,
    sorter: SorterResult<ApprovalTask> | SorterResult<ApprovalTask>[]
  ) => {
    const sortInfo = Array.isArray(sorter) ? sorter[0] : sorter;
    setFilters((prev) => ({
      ...prev,
      page: pagination.current || 1,
      pageSize: pagination.pageSize || APP_CONFIG.DEFAULT_PAGE_SIZE,
      sortBy: sortInfo.field?.toString(),
      sortOrder: sortInfo.order === 'ascend' ? 'asc' : 'desc',
    }));
  }, []);

  // 筛选变化
  const handleFilterChange = useCallback((key: string, value?: string) => {
    setFilters((prev) => ({
      ...prev,
      page: 1,
      [key]: value,
    }));
  }, []);

  // 搜索
  const handleSearch = useCallback(() => {
    setFilters((prev) => ({
      ...prev,
      page: 1,
      search: searchText || undefined,
    }));
  }, [searchText]);

  // 统计数据
  const pendingCount = useMemo(() => {
    return data?.items.filter((item) => item.status === 'pending').length || 0;
  }, [data]);

  return (
    <PageLayout>
    <div className="space-y-4">
      {/* Header */}
      <div className="mb-6">
        <Title level={4} className="!mb-2">
          审批中心
          {pendingCount > 0 && (
            <Badge count={pendingCount} className="ml-2" />
          )}
        </Title>
        <Text type="secondary">
          管理待审批任务，支持快速筛选和批量操作
        </Text>
      </div>

      {/* Filters */}
      <Card className="mb-4">
        <Space wrap size="middle">
          <Input.Search
            placeholder="搜索审批标题"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 250 }}
            prefix={<Search className="w-4 h-4 text-gray-400" />}
            allowClear
          />
          <Select
            placeholder="状态筛选"
            value={filters.status}
            onChange={(value) => handleFilterChange('status', value)}
            style={{ width: 120 }}
            allowClear
            options={[
              { value: 'pending', label: '待审批' },
              { value: 'approved', label: '已通过' },
              { value: 'rejected', label: '已拒绝' },
              { value: 'expired', label: '已过期' },
              { value: 'cancelled', label: '已取消' },
            ]}
          />
          <Select
            placeholder="优先级"
            value={filters.priority}
            onChange={(value) => handleFilterChange('priority', value)}
            style={{ width: 100 }}
            allowClear
            options={[
              { value: 'urgent', label: '紧急' },
              { value: 'high', label: '高' },
              { value: 'normal', label: '普通' },
              { value: 'low', label: '低' },
            ]}
          />
          <Select
            placeholder="类型"
            value={filters.taskType}
            onChange={(value) => handleFilterChange('taskType', value)}
            style={{ width: 140 }}
            allowClear
            options={[
              { value: 'tool_approval', label: '工具审批' },
              { value: 'sensitive_action', label: '敏感操作' },
              { value: 'high_value_transaction', label: '高价值交易' },
            ]}
          />
          <Button
            icon={<RefreshCw className="w-4 h-4" />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            刷新
          </Button>
        </Space>
      </Card>

      {/* Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={data?.items || []}
          rowKey="id"
          loading={isLoading}
          pagination={{
            current: filters.page,
            pageSize: filters.pageSize,
            total: data?.total || 0,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
          }}
          onChange={handleTableChange}
          locale={{
            emptyText: (
              <EmptyState
                description="暂无审批任务"
                action={
                  filters.status || filters.priority || filters.taskType
                    ? {
                        label: '清除筛选',
                        onClick: () => setFilters({ page: 1, pageSize: APP_CONFIG.DEFAULT_PAGE_SIZE }),
                      }
                    : undefined
                }
              />
            ),
          }}
        />
      </Card>

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
          setActionModal({ visible: false, type: 'approve', approval: null });
          setComment('');
        }}
        onOk={confirmAction}
        confirmLoading={approveMutation.isPending || rejectMutation.isPending}
        okText={actionModal.type === 'approve' ? '确认通过' : '确认拒绝'}
        okButtonProps={{ danger: actionModal.type === 'reject' }}
      >
        {actionModal.approval && (
          <div className="py-4">
            <div className="mb-4 p-3 bg-gray-50 rounded">
              <Text strong>{actionModal.approval.title}</Text>
              <br />
              <Text type="secondary" className="text-sm">
                {actionModal.approval.description}
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
        )}
      </Modal>
    </div>
    </PageLayout>
  );
}

export default Route;