import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Card,
  Descriptions,
  Tag,
  Button,
  Space,
  Typography,
  Divider,
  Table,
  Switch,
  message,
  Tabs,
  Empty,
} from 'antd';
import {
  ArrowLeftOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { getTool, getToolInvocations, enableTool, disableTool } from '@/services/tools';
import { usePermission } from '@/hooks/usePermission';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ROUTES } from '@/constants/routes';
import type { ToolInvocation, ToolStatus } from '@/types/tools';
import dayjs from 'dayjs';

export const Route = createFileRoute('/tools/$name')();

const { Text, Paragraph } = Typography;

/** 风险等级颜色映射 */
const RISK_COLORS: Record<string, string> = {
  low: 'green',
  medium: 'blue',
  high: 'orange',
  critical: 'red',
};

/** 状态颜色映射 */
const STATUS_COLORS: Record<ToolStatus, string> = {
  draft: 'default',
  active: 'success',
  disabled: 'error',
  deprecated: 'warning',
  sunset: 'default',
};

/** 调用状态颜色映射 */
const INVOCATION_STATUS_COLORS: Record<string, string> = {
  pending: 'processing',
  success: 'success',
  failed: 'error',
  rejected: 'warning',
  timeout: 'default',
};

/** 类型标签映射 */
const CATEGORY_LABELS: Record<string, string> = {
  query: '查询',
  write: '写入',
  external: '外部',
};

export default function ToolDetailPage() {
  const { name } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAdmin, hasPermission } = usePermission();
  const canManage = isAdmin || hasPermission('tool:write');
  const [invocationPage, setInvocationPage] = useState({ current: 1, pageSize: 10 });

  // 查询工具详情
  const {
    data: tool,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['tool', name],
    queryFn: () => getTool(name),
  });

  // 查询调用历史
  const { data: invocations, isLoading: invocationsLoading } = useQuery({
    queryKey: ['tool-invocations', name, invocationPage],
    queryFn: () =>
      getToolInvocations({
        toolName: name,
        pageNumber: invocationPage.current,
        pageSize: invocationPage.pageSize,
      }),
    enabled: !!tool,
  });

  // 启用/禁用 Mutation
  const toggleMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      return enabled ? enableTool(name) : disableTool(name);
    },
    onSuccess: () => {
      message.success('操作成功');
      queryClient.invalidateQueries({ queryKey: ['tool', name] });
      queryClient.invalidateQueries({ queryKey: ['tools'] });
    },
    onError: () => {
      message.error('操作失败');
    },
  });

  // 调用历史表格列
  const invocationColumns = [
    {
      title: '调用时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: 'Run ID',
      dataIndex: 'run_id',
      key: 'run_id',
      width: 200,
      ellipsis: true,
      render: (runId: string) => (
        <Text copyable style={{ fontSize: 12 }}>
          {runId}
        </Text>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={INVOCATION_STATUS_COLORS[status]}>{status}</Tag>
      ),
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      width: 100,
      render: (ms: number) => (ms ? `${ms}ms` : '-'),
    },
    {
      title: '缓存',
      dataIndex: 'was_cached',
      key: 'was_cached',
      width: 80,
      render: (cached: boolean) =>
        cached ? (
          <CheckCircleOutlined style={{ color: '#52c41a' }} />
        ) : (
          <CloseCircleOutlined style={{ color: '#d9d9d9' }} />
        ),
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      render: (msg: string) =>
        msg ? <Text type="danger">{msg}</Text> : '-',
    },
  ];

  if (isLoading) {
    return <LoadingState tip="加载工具详情..." />;
  }

  if (!tool) {
    return (
      <Card>
        <Empty description="工具不存在" />
        <div className="text-center mt-4">
          <Button onClick={() => navigate({ to: ROUTES.TOOLS })}>
            返回工具列表
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* 顶部操作栏 */}
      <Card>
        <div className="flex items-center justify-between">
          <Space>
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate({ to: ROUTES.TOOLS })}
            >
              返回
            </Button>
            <Divider type="vertical" />
            <Text strong style={{ fontSize: 18 }}>
              {tool.name}
            </Text>
            <Tag color={STATUS_COLORS[tool.status]}>{tool.status}</Tag>
          </Space>
          <Space>
            <Button
              icon={<ReloadOutlined spin={isFetching} />}
              onClick={() => refetch()}
            >
              刷新
            </Button>
            {canManage && (
              <Switch
                checked={tool.enabled}
                disabled={
                  tool.status === 'deprecated' ||
                  tool.status === 'sunset'
                }
                loading={toggleMutation.isPending}
                checkedChildren="已启用"
                unCheckedChildren="已禁用"
                onChange={(checked) => toggleMutation.mutate(checked)}
              />
            )}
          </Space>
        </div>
      </Card>

      {/* 详情内容 */}
      <Tabs
        defaultActiveKey="info"
        items={[
          {
            key: 'info',
            label: '基本信息',
            children: (
              <Card>
                <Descriptions column={2} bordered size="small">
                  <Descriptions.Item label="名称">{tool.name}</Descriptions.Item>
                  <Descriptions.Item label="版本">
                    <Tag>{tool.version}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="类型">
                    <Tag color="blue">
                      {CATEGORY_LABELS[tool.category] || tool.category}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="风险等级">
                    <Tag color={RISK_COLORS[tool.risk_level]}>
                      {tool.risk_level.toUpperCase()}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="状态" span={2}>
                    <Tag color={STATUS_COLORS[tool.status]}>{tool.status}</Tag>
                    {tool.enabled ? (
                      <Tag color="success">已启用</Tag>
                    ) : (
                      <Tag color="error">已禁用</Tag>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label="描述" span={2}>
                    {tool.description}
                  </Descriptions.Item>
                  <Descriptions.Item label="端点" span={2}>
                    <Text copyable>{tool.endpoint}</Text>
                  </Descriptions.Item>
                  <Descriptions.Item label="HTTP 方法">
                    <Tag>{tool.method}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="超时时间">
                    {tool.timeout_ms}ms
                  </Descriptions.Item>
                  <Descriptions.Item label="认证类型">
                    {tool.auth_type}
                  </Descriptions.Item>
                  <Descriptions.Item label="所属团队">
                    {tool.owner_team || '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="允许角色" span={2}>
                    {tool.allowed_roles.map((role) => (
                      <Tag key={role}>{role}</Tag>
                    ))}
                  </Descriptions.Item>
                  <Descriptions.Item label="每日配额">
                    {tool.daily_quota_per_user
                      ? `${tool.daily_quota_per_user} 次/用户`
                      : '不限制'}
                  </Descriptions.Item>
                  <Descriptions.Item label="标签">
                    {tool.tags.length > 0
                      ? tool.tags.map((tag) => <Tag key={tag}>{tag}</Tag>)
                      : '-'}
                  </Descriptions.Item>
                  <Descriptions.Item label="创建时间">
                    {dayjs(tool.created_at).format('YYYY-MM-DD HH:mm:ss')}
                  </Descriptions.Item>
                  <Descriptions.Item label="更新时间">
                    {dayjs(tool.updated_at).format('YYYY-MM-DD HH:mm:ss')}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            ),
          },
          {
            key: 'schema',
            label: '参数 Schema',
            children: (
              <Card>
                <Paragraph>
                  <pre
                    style={{
                      backgroundColor: '#f5f5f5',
                      padding: 16,
                      borderRadius: 4,
                      overflow: 'auto',
                      maxHeight: 500,
                    }}
                  >
                    {JSON.stringify(tool.parameters, null, 2)}
                  </pre>
                </Paragraph>
              </Card>
            ),
          },
          {
            key: 'history',
            label: '调用历史',
            children: (
              <Card>
                <Table
                  columns={invocationColumns}
                  dataSource={invocations?.items}
                  rowKey="id"
                  loading={invocationsLoading}
                  pagination={{
                    current: invocationPage.current,
                    pageSize: invocationPage.pageSize,
                    total: invocations?.total_count ?? 0,
                    showSizeChanger: true,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page, pageSize) => {
                      setInvocationPage({ current: page, pageSize });
                    },
                  }}
                  locale={{
                    emptyText: <Empty description="暂无调用记录" />,
                  }}
                />
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
