import { createFileRoute, Link } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useMemo } from 'react';
import {
  Table,
  Card,
  Button,
  Input,
  Select,
  Switch,
  Tag,
  Space,
  message,
  Typography,
} from 'antd';
import {
  SearchOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { getTools, enableTool, disableTool } from '@/services/tools';
import { usePermission } from '@/hooks/usePermission';
import { LoadingState } from '@/components/feedback/LoadingState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageLayout } from '@/components/layout/PageLayout';
import { ROUTES } from '@/constants/routes';
import type { ToolDefinition, ToolStatus } from '@/types/tools';
import dayjs from 'dayjs';

export const Route = createFileRoute('/tools/')({
  component: ToolsPage,
});

const { Text } = Typography;

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

/** 类型标签映射 */
const CATEGORY_LABELS: Record<string, string> = {
  query: '查询',
  write: '写入',
  external: '外部',
};

export default function ToolsPage() {
  const queryClient = useQueryClient();
  const { isAdmin, hasPermission } = usePermission();
  const canManage = isAdmin || hasPermission('tool:write');

  // 筛选状态
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [riskFilter, setRiskFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<ToolStatus | undefined>();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10 });

  // 查询工具列表
  const {
    data,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['tools', search, categoryFilter, riskFilter, statusFilter, pagination],
    queryFn: () =>
      getTools({
        search: search || undefined,
        category: categoryFilter as 'query' | 'write' | 'external' | undefined,
        riskLevel: riskFilter as 'low' | 'medium' | 'high' | 'critical' | undefined,
        status: statusFilter,
        pageNumber: pagination.current,
        pageSize: pagination.pageSize,
      }),
    placeholderData: (prev) => prev,
  });

  // 启用/禁用 Mutation
  const toggleMutation = useMutation({
    mutationFn: async ({ name, enabled }: { name: string; enabled: boolean }) => {
      return enabled ? enableTool(name) : disableTool(name);
    },
    onSuccess: () => {
      message.success('操作成功');
      queryClient.invalidateQueries({ queryKey: ['tools'] });
    },
    onError: () => {
      message.error('操作失败');
    },
  });

  // 表格列定义
  const columns = useMemo(
    () => [
      {
        title: '名称',
        dataIndex: 'name',
        key: 'name',
        width: 200,
        render: (name: string) => (
          <Link to={ROUTES.TOOLS_DETAIL} params={{ name }} className="text-blue-600 hover:underline">
            {name}
          </Link>
        ),
      },
      {
        title: '描述',
        dataIndex: 'description',
        key: 'description',
        ellipsis: true,
        width: 300,
      },
      {
        title: '版本',
        dataIndex: 'version',
        key: 'version',
        width: 80,
        render: (version: string) => <Tag>{version}</Tag>,
      },
      {
        title: '类型',
        dataIndex: 'category',
        key: 'category',
        width: 80,
        render: (category: string) => (
          <Tag color="blue">{CATEGORY_LABELS[category] || category}</Tag>
        ),
      },
      {
        title: '风险等级',
        dataIndex: 'risk_level',
        key: 'risk_level',
        width: 100,
        render: (risk: string) => (
          <Tag color={RISK_COLORS[risk]}>{risk.toUpperCase()}</Tag>
        ),
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (status: ToolStatus) => (
          <Tag color={STATUS_COLORS[status]}>{status}</Tag>
        ),
      },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        key: 'updated_at',
        width: 160,
        render: (date: string) => dayjs(date).format('YYYY-MM-DD HH:mm'),
      },
      {
        title: '启用',
        dataIndex: 'enabled',
        key: 'enabled',
        width: 80,
        render: (enabled: boolean, record: ToolDefinition) => (
          <Switch
            checked={enabled}
            disabled={!canManage || record.status === 'deprecated' || record.status === 'sunset'}
            loading={toggleMutation.isPending}
            onChange={(checked) => {
              toggleMutation.mutate({ name: record.name, enabled: checked });
            }}
          />
        ),
      },
      {
        title: '操作',
        key: 'action',
        width: 120,
        render: (_: unknown, record: ToolDefinition) => (
          <Space>
            <Link to={ROUTES.TOOLS_DETAIL} params={{ name: record.name }}>
              <Button type="link" size="small">
                详情
              </Button>
            </Link>
          </Space>
        ),
      },
    ],
    [canManage, toggleMutation]
  );

  if (isLoading) {
    return <PageLayout><LoadingState tip="加载工具列表..." /></PageLayout>;
  }

  return (
    <PageLayout>
    <div className="space-y-4">
      <Card>
        <div className="flex items-center justify-between mb-4">
          <Text strong style={{ fontSize: 16 }}>
            工具管理
          </Text>
          <Space>
            {canManage && (
              <Link to={ROUTES.TOOLS_REGISTER}>
                <Button type="primary" icon={<PlusOutlined />}>
                  注册工具
                </Button>
              </Link>
            )}
            <Button
              icon={<ReloadOutlined spin={isFetching} />}
              onClick={() => refetch()}
            >
              刷新
            </Button>
          </Space>
        </div>

        {/* 筛选栏 */}
        <div className="flex flex-wrap gap-4 mb-4">
          <Input
            placeholder="搜索工具名称/描述"
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPagination((p) => ({ ...p, current: 1 }));
            }}
            style={{ width: 250 }}
            allowClear
          />
          <Select
            placeholder="类型"
            allowClear
            value={categoryFilter}
            onChange={(v) => {
              setCategoryFilter(v);
              setPagination((p) => ({ ...p, current: 1 }));
            }}
            style={{ width: 120 }}
            options={[
              { value: 'query', label: '查询' },
              { value: 'write', label: '写入' },
              { value: 'external', label: '外部' },
            ]}
          />
          <Select
            placeholder="风险等级"
            allowClear
            value={riskFilter}
            onChange={(v) => {
              setRiskFilter(v);
              setPagination((p) => ({ ...p, current: 1 }));
            }}
            style={{ width: 120 }}
            options={[
              { value: 'low', label: '低' },
              { value: 'medium', label: '中' },
              { value: 'high', label: '高' },
              { value: 'critical', label: '严重' },
            ]}
          />
          <Select
            placeholder="状态"
            allowClear
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v);
              setPagination((p) => ({ ...p, current: 1 }));
            }}
            style={{ width: 120 }}
            options={[
              { value: 'draft', label: '草稿' },
              { value: 'active', label: '活跃' },
              { value: 'disabled', label: '禁用' },
              { value: 'deprecated', label: '废弃' },
              { value: 'sunset', label: '下线' },
            ]}
          />
        </div>

        {/* 表格 */}
        <Table
          columns={columns}
          dataSource={data?.items}
          rowKey="name"
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: data?.total_count ?? 0,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPagination({ current: page, pageSize });
            },
          }}
          loading={isFetching}
          locale={{
            emptyText: search || categoryFilter || riskFilter || statusFilter ? (
              <EmptyState description="未找到匹配的工具" />
            ) : (
              <EmptyState
                description="暂无工具"
                action={
                  canManage
                    ? {
                        label: '注册工具',
                        onClick: () => {
                          window.location.href = ROUTES.TOOLS_REGISTER;
                        },
                      }
                    : undefined
                }
              />
            ),
          }}
        />
      </Card>
    </div>
    </PageLayout>
  );
}
