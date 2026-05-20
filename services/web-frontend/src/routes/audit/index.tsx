import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import {
  Table,
  Card,
  Button,
  Space,
  Tag,
  DatePicker,
  Select,
  Input,
  Tooltip,
  Modal,
  Descriptions,
  message,
  Popconfirm,
  Badge,
} from 'antd';
import {
  Download,
  RefreshCw,
  Search,
  Eye,
  AlertCircle,
  Info,
  AlertTriangle,
  XCircle,
} from 'lucide-react';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import type { FilterValue } from 'antd/es/table/interface';
import { PageLayout } from '@/components/layout/PageLayout';
import { getAuditEvents, exportAuditEvents, getAuditEventTypes } from '@/services/audit';
import type { AuditEvent, AuditQueryParams } from '@/types/audit';
import { formatDateTime, formatRelativeTime } from '@/utils/date';
import { formatNumber } from '@/utils/format';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { useWebSocket } from '@/hooks/useWebSocket';

const { RangePicker } = DatePicker;

export const Route = createFileRoute('/audit/')({
  component: AuditLogPage,
  beforeLoad: () => {
    // 权限检查可以在路由层做
  },
});

type SeverityConfig = {
  color: string;
  icon: React.ReactNode;
  label: string;
};

const severityConfig: Record<string, SeverityConfig> = {
  info: { color: 'blue', icon: <Info className="w-4 h-4" />, label: '信息' },
  warn: { color: 'orange', icon: <AlertTriangle className="w-4 h-4" />, label: '警告' },
  error: { color: 'red', icon: <AlertCircle className="w-4 h-4" />, label: '错误' },
  critical: { color: 'magenta', icon: <XCircle className="w-4 h-4" />, label: '严重' },
};

const categoryLabels: Record<string, string> = {
  lifecycle: '生命周期',
  security: '安全',
  business: '业务',
  system: '系统',
};

function AuditLogPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();

  // 筛选状态
  const [params, setParams] = useState<AuditQueryParams>({
    pageNumber: 1,
    pageSize: 20,
  });
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [detailEvent, setDetailEvent] = useState<AuditEvent | null>(null);

  // 查询审计事件
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['audit-events', params],
    queryFn: () => getAuditEvents(params),
  });

  // 查询事件类型列表
  const { data: eventTypes } = useQuery({
    queryKey: ['audit-event-types'],
    queryFn: getAuditEventTypes,
  });

  // WebSocket 实时更新
  const wsUrl = `${import.meta.env.VITE_WS_URL || 'ws://localhost:8080/ws'}/audit`;
  useWebSocket({
    url: wsUrl,
    onMessage: (data: { type: string; event?: AuditEvent }) => {
      if (data.type === 'new_event') {
        queryClient.invalidateQueries({ queryKey: ['audit-events'] });
        message.info('收到新的审计事件');
      }
    },
  });

  // 分页变化
  const handleTableChange = useCallback(
    (pagination: TablePaginationConfig, filters: Record<string, FilterValue | null>) => {
      setParams((prev) => ({
        ...prev,
        pageNumber: pagination.current || 1,
        pageSize: pagination.pageSize || 20,
        severity: filters.severity?.[0] as string | undefined,
        eventCategory: filters.event_category?.[0] as string | undefined,
      }));
    },
    []
  );

  // 导出
  const handleExport = useCallback(
    async (format: 'csv' | 'json') => {
      if (!hasPermission(Permissions.AUDIT_EXPORT)) {
        message.warning('没有导出权限');
        return;
      }

      try {
        const blob = await exportAuditEvents(
          {
            ...params,
            startTime: params.startTime,
            endTime: params.endTime,
          },
          format
        );

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit-events.${format}`;
        a.click();
        window.URL.revokeObjectURL(url);

        message.success('导出成功');
      } catch {
        message.error('导出失败');
      }
    },
    [params, hasPermission]
  );

  // 表格列定义
  const columns: ColumnsType<AuditEvent> = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (value: string) => (
        <Tooltip title={formatDateTime(value)}>
          <span className="text-gray-600">{formatRelativeTime(value)}</span>
        </Tooltip>
      ),
      sorter: true,
    },
    {
      title: '严重级别',
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (severity: string) => {
        const config = severityConfig[severity] || severityConfig.info;
        return (
          <Tag color={config.color} icon={config.icon}>
            {config.label}
          </Tag>
        );
      },
      filters: [
        { text: '信息', value: 'info' },
        { text: '警告', value: 'warn' },
        { text: '错误', value: 'error' },
        { text: '严重', value: 'critical' },
      ],
      filtered: !!params.severity,
      filteredValue: params.severity ? [params.severity] : null,
    },
    {
      title: '分类',
      dataIndex: 'event_category',
      key: 'event_category',
      width: 100,
      render: (category: string) => categoryLabels[category] || category,
      filters: [
        { text: '生命周期', value: 'lifecycle' },
        { text: '安全', value: 'security' },
        { text: '业务', value: 'business' },
        { text: '系统', value: 'system' },
      ],
      filtered: !!params.eventCategory,
      filteredValue: params.eventCategory ? [params.eventCategory] : null,
    },
    {
      title: '事件类型',
      dataIndex: 'event_type',
      key: 'event_type',
      width: 150,
      ellipsis: true,
    },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      width: 120,
      ellipsis: true,
    },
    {
      title: '用户',
      dataIndex: 'user_id',
      key: 'user_id',
      width: 120,
      ellipsis: true,
    },
    {
      title: '来源服务',
      dataIndex: 'source_service',
      key: 'source_service',
      width: 120,
      ellipsis: true,
    },
    {
      title: '请求ID',
      dataIndex: 'request_id',
      key: 'request_id',
      width: 150,
      ellipsis: true,
      render: (value: string) => (
        <Tooltip title={value}>
          <span className="text-gray-500 text-xs font-mono">{value.slice(0, 16)}...</span>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: AuditEvent) => (
        <Button
          type="text"
          icon={<Eye className="w-4 h-4" />}
          onClick={() => setDetailEvent(record)}
        />
      ),
    },
  ];

  return (
    <PageLayout>
      <div className="space-y-4">
        {/* 筛选栏 */}
        <Card>
          <div className="flex flex-wrap items-center gap-4">
            <RangePicker
              showTime
              onChange={(dates) => {
                setParams((prev) => ({
                  ...prev,
                  startTime: dates?.[0]?.toISOString(),
                  endTime: dates?.[1]?.toISOString(),
                  pageNumber: 1,
                }));
              }}
            />

            <Select
              placeholder="事件类型"
              allowClear
              style={{ width: 150 }}
              onChange={(value) =>
                setParams((prev) => ({ ...prev, eventType: value, pageNumber: 1 }))
              }
            >
              {eventTypes?.map((type) => (
                <Select.Option key={type} value={type}>
                  {type}
                </Select.Option>
              ))}
            </Select>

            <Input
              placeholder="用户ID"
              prefix={<Search className="w-4 h-4 text-gray-400" />}
              style={{ width: 150 }}
              onChange={(e) =>
                setParams((prev) => ({ ...prev, userId: e.target.value || undefined, pageNumber: 1 }))
              }
            />

            <Input
              placeholder="资源ID"
              prefix={<Search className="w-4 h-4 text-gray-400" />}
              style={{ width: 150 }}
              onChange={(e) =>
                setParams((prev) => ({ ...prev, resourceId: e.target.value || undefined, pageNumber: 1 }))
              }
            />

            <Space>
              <Button icon={<RefreshCw className="w-4 h-4" />} onClick={() => refetch()}>
                刷新
              </Button>
            </Space>
          </div>
        </Card>

        {/* 表格 */}
        <Card>
          <div className="mb-4 flex justify-between items-center">
            <div className="text-gray-600">
              共 <span className="font-medium">{formatNumber(data?.total_count || 0)}</span> 条记录
            </div>
            <Space>
              <Button
                icon={<Download className="w-4 h-4" />}
                onClick={() => handleExport('csv')}
                disabled={!hasPermission(Permissions.AUDIT_EXPORT)}
              >
                导出 CSV
              </Button>
              <Button
                icon={<Download className="w-4 h-4" />}
                onClick={() => handleExport('json')}
                disabled={!hasPermission(Permissions.AUDIT_EXPORT)}
              >
                导出 JSON
              </Button>
            </Space>
          </div>

          <Table
            columns={columns}
            dataSource={data?.items || []}
            rowKey="id"
            loading={isLoading}
            pagination={{
              current: params.pageNumber,
              pageSize: params.pageSize,
              total: data?.total_count || 0,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${formatNumber(total)} 条`,
            }}
            onChange={handleTableChange}
            rowSelection={{
              selectedRowKeys,
              onChange: setSelectedRowKeys,
            }}
            scroll={{ x: 1200 }}
          />
        </Card>
      </div>

      {/* 详情弹窗 */}
      <Modal
        title="审计事件详情"
        open={!!detailEvent}
        onCancel={() => setDetailEvent(null)}
        footer={null}
        width={700}
      >
        {detailEvent && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="事件ID" span={2}>
              <span className="font-mono text-xs">{detailEvent.event_id}</span>
            </Descriptions.Item>
            <Descriptions.Item label="时间">{formatDateTime(detailEvent.created_at)}</Descriptions.Item>
            <Descriptions.Item label="严重级别">
              <Badge
                status={
                  detailEvent.severity === 'critical'
                    ? 'error'
                    : detailEvent.severity === 'error'
                    ? 'error'
                    : detailEvent.severity === 'warn'
                    ? 'warning'
                    : 'success'
                }
                text={severityConfig[detailEvent.severity]?.label || detailEvent.severity}
              />
            </Descriptions.Item>
            <Descriptions.Item label="事件类型">{detailEvent.event_type}</Descriptions.Item>
            <Descriptions.Item label="分类">
              {categoryLabels[detailEvent.event_category] || detailEvent.event_category}
            </Descriptions.Item>
            <Descriptions.Item label="操作">{detailEvent.action}</Descriptions.Item>
            <Descriptions.Item label="用户ID">{detailEvent.user_id}</Descriptions.Item>
            <Descriptions.Item label="租户ID">{detailEvent.tenant_id}</Descriptions.Item>
            <Descriptions.Item label="资源类型">{detailEvent.resource_type || '-'}</Descriptions.Item>
            <Descriptions.Item label="资源ID">{detailEvent.resource_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="来源服务">{detailEvent.source_service}</Descriptions.Item>
            <Descriptions.Item label="IP地址">{detailEvent.ip_address || '-'}</Descriptions.Item>
            <Descriptions.Item label="请求ID" span={2}>
              <span className="font-mono text-xs">{detailEvent.request_id}</span>
            </Descriptions.Item>
            <Descriptions.Item label="追踪ID" span={2}>
              <span className="font-mono text-xs">{detailEvent.trace_id}</span>
            </Descriptions.Item>
            {detailEvent.details && (
              <Descriptions.Item label="详情" span={2}>
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto max-h-40">
                  {JSON.stringify(detailEvent.details, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {detailEvent.before_state && (
              <Descriptions.Item label="变更前" span={2}>
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto max-h-40">
                  {JSON.stringify(detailEvent.before_state, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
            {detailEvent.after_state && (
              <Descriptions.Item label="变更后" span={2}>
                <pre className="bg-gray-50 p-2 rounded text-xs overflow-auto max-h-40">
                  {JSON.stringify(detailEvent.after_state, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </PageLayout>
  );
}

export default Route;
