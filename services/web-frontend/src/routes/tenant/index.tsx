import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  Switch,
  Button,
  Divider,
  message,
  Spin,
  Alert,
  Typography,
  Descriptions,
  Tag,
  Progress,
  Row,
  Col,
  Tooltip,
  Space,
} from 'antd';
import { Save, RefreshCw, InfoCircle, Shield, Database, Bot } from 'lucide-react';
import { tenantService } from '@/services/tenant';
import type { TenantConfig } from '@/services/tenant';
import { LoadingState } from '@/components/feedback/LoadingState';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { useAuthStore } from '@/stores/authStore';
import { formatDateTime } from '@/utils/date';
import { formatCurrency } from '@/utils/format';

const { Title, Text } = Typography;

export const Route = createFileRoute('/tenant/')({
  component: TenantConfigPage,
});

const tierConfig: Record<string, { color: string; label: string }> = {
  free: { color: 'default', label: '免费版' },
  standard: { color: 'blue', label: '标准版' },
  premium: { color: 'gold', label: '高级版' },
  enterprise: { color: 'purple', label: '企业版' },
};

function TenantConfigPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();
  const { tenant } = useAuthStore();
  const [form] = Form.useForm();

  const canEdit = hasPermission(Permissions.TENANT_WRITE);

  // 查询租户配置
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['tenant-config', tenant?.id],
    queryFn: () => tenantService.getConfig(tenant?.id || ''),
    enabled: !!tenant?.id,
  });

  // 查询配额使用情况
  const { data: quotaUsage } = useQuery({
    queryKey: ['tenant-quota', tenant?.id],
    queryFn: () => tenantService.getQuotaUsage(tenant?.id || ''),
    enabled: !!tenant?.id,
  });

  // 更新配置
  const updateMutation = useMutation({
    mutationFn: (values: Partial<TenantConfig['settings']>) =>
      tenantService.updateSettings(tenant?.id || '', values),
    onSuccess: () => {
      message.success('配置已保存');
      queryClient.invalidateQueries({ queryKey: ['tenant-config'] });
    },
    onError: () => {
      message.error('保存失败');
    },
  });

  // 重置配置
  const resetMutation = useMutation({
    mutationFn: () => tenantService.resetSettings(tenant?.id || ''),
    onSuccess: () => {
      message.success('已重置为默认配置');
      queryClient.invalidateQueries({ queryKey: ['tenant-config'] });
    },
    onError: () => {
      message.error('重置失败');
    },
  });

  // 表单初始化
  useEffect(() => {
    if (data) {
      form.setFieldsValue(data.settings);
    }
  }, [data, form]);

  // 保存配置
  const handleSave = useCallback(() => {
    form.validateFields().then((values) => {
      updateMutation.mutate(values);
    });
  }, [form, updateMutation]);

  // 重置配置
  const handleReset = useCallback(() => {
    resetMutation.mutate();
  }, [resetMutation]);

  if (isLoading) {
    return <LoadingState />;
  }

  if (!data) {
    return (
      <div className="p-6">
        <Alert type="error" message="无法获取租户配置" showIcon />
      </div>
    );
  }

  const tier = tierConfig[data.tier] || tierConfig.free;

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <Title level={4} className="!mb-2">
          租户配置
        </Title>
        <Text type="secondary">
          查看和管理当前租户的配置与配额
        </Text>
      </div>

      {/* 租户信息 */}
      <Card className="mb-4">
        <Descriptions column={3} bordered size="small">
          <Descriptions.Item label="租户名称">{data.name}</Descriptions.Item>
          <Descriptions.Item label="租户ID">
            <Text copyable className="text-xs">{data.id}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="等级">
            <Tag color={tier.color}>{tier.label}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">{formatDateTime(data.created_at)}</Descriptions.Item>
          <Descriptions.Item label="更新时间">{formatDateTime(data.updated_at)}</Descriptions.Item>
          <Descriptions.Item label="功能特性">
            <Space>
              {data.features.map((f) => (
                <Tag key={f}>{f}</Tag>
              ))}
            </Space>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 配额使用 */}
      {quotaUsage && (
        <Card className="mb-4" title="配额使用情况">
          <Row gutter={16}>
            <Col span={8}>
              <div className="text-center">
                <Text type="secondary" className="block mb-2">每日 Token</Text>
                <Progress
                  type="circle"
                  percent={Math.round((quotaUsage.daily_tokens_used / quotaUsage.daily_tokens_limit) * 100)}
                  format={(percent) => `${quotaUsage.daily_tokens_used.toLocaleString()} / ${quotaUsage.daily_tokens_limit.toLocaleString()}`}
                />
              </div>
            </Col>
            <Col span={8}>
              <div className="text-center">
                <Text type="secondary" className="block mb-2">月度成本</Text>
                <Progress
                  type="circle"
                  percent={Math.round((quotaUsage.monthly_cost_used / quotaUsage.monthly_cost_limit) * 100)}
                  format={(percent) => `${formatCurrency(quotaUsage.monthly_cost_used)} / ${formatCurrency(quotaUsage.monthly_cost_limit)}`}
                  strokeColor={quotaUsage.monthly_cost_used > quotaUsage.monthly_cost_limit * 0.8 ? '#ff4d4f' : undefined}
                />
              </div>
            </Col>
            <Col span={8}>
              <div className="text-center">
                <Text type="secondary" className="block mb-2">并发任务</Text>
                <Progress
                  type="circle"
                  percent={Math.round((quotaUsage.concurrent_runs_current / quotaUsage.concurrent_runs_limit) * 100)}
                  format={(percent) => `${quotaUsage.concurrent_runs_current} / ${quotaUsage.concurrent_runs_limit}`}
                />
              </div>
            </Col>
          </Row>
        </Card>
      )}

      {/* 权限提示 */}
      {!canEdit && (
        <Alert
          type="warning"
          message="您没有修改租户配置的权限"
          description="请联系管理员获取权限"
          showIcon
          className="mb-4"
        />
      )}

      {/* 配置表单 */}
      <Card title="运行配置">
        <Form
          form={form}
          layout="vertical"
          disabled={!canEdit}
          initialValues={data.settings}
        >
          <Row gutter={24}>
            <Col span={12}>
              <Form.Item
                name="max_sessions_per_user"
                label={
                  <span className="flex items-center gap-1">
                    <Database className="w-4 h-4" />
                    最大会话数/用户
                    <Tooltip title="每个用户最多可创建的会话数量">
                      <InfoCircle className="w-3 h-3 text-gray-400" />
                    </Tooltip>
                  </span>
                }
              >
                <Input type="number" min={1} max={1000} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="max_tokens_per_day"
                label={
                  <span className="flex items-center gap-1">
                    <Database className="w-4 h-4" />
                    每日最大 Token
                    <Tooltip title="每日可消耗的最大 Token 数量">
                      <InfoCircle className="w-3 h-3 text-gray-400" />
                    </Tooltip>
                  </span>
                }
              >
                <Input type="number" min={1000} max={10000000} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={24}>
            <Col span={12}>
              <Form.Item
                name="max_concurrent_runs"
                label={
                  <span className="flex items-center gap-1">
                    <Bot className="w-4 h-4" />
                    最大并发任务
                    <Tooltip title="同时运行的 Agent 任务数量上限">
                      <InfoCircle className="w-3 h-3 text-gray-400" />
                    </Tooltip>
                  </span>
                }
              >
                <Input type="number" min={1} max={100} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="data_retention_days"
                label="数据保留天数"
              >
                <Input type="number" min={1} max={365} />
              </Form.Item>
            </Col>
          </Row>

          <Divider>模型设置</Divider>

          <Row gutter={24}>
            <Col span={12}>
              <Form.Item
                name="default_model"
                label="默认模型"
              >
                <Select>
                  <Select.Option value="qwen-plus">Qwen Plus</Select.Option>
                  <Select.Option value="qwen-max">Qwen Max</Select.Option>
                  <Select.Option value="deepseek-chat">DeepSeek Chat</Select.Option>
                  <Select.Option value="glm-4">GLM-4</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="allowed_models"
                label="允许使用的模型"
              >
                <Select mode="multiple">
                  <Select.Option value="qwen-plus">Qwen Plus</Select.Option>
                  <Select.Option value="qwen-max">Qwen Max</Select.Option>
                  <Select.Option value="deepseek-chat">DeepSeek Chat</Select.Option>
                  <Select.Option value="glm-4">GLM-4</Select.Option>
                  <Select.Option value="gpt-4">GPT-4</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Divider>功能开关</Divider>

          <Row gutter={24}>
            <Col span={8}>
              <Form.Item
                name="enable_knowledge_base"
                label={
                  <span className="flex items-center gap-1">
                    <Database className="w-4 h-4" />
                    知识库
                  </span>
                }
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="enable_multi_agent"
                label={
                  <span className="flex items-center gap-1">
                    <Bot className="w-4 h-4" />
                    多 Agent
                  </span>
                }
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="enable_audit_log"
                label={
                  <span className="flex items-center gap-1">
                    <Shield className="w-4 h-4" />
                    审计日志
                  </span>
                }
                valuePropName="checked"
              >
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          {canEdit && (
            <div className="flex justify-end gap-4 mt-4">
              <Button onClick={handleReset} loading={resetMutation.isPending}>
                重置为默认
              </Button>
              <Button
                type="primary"
                icon={<Save className="w-4 h-4" />}
                onClick={handleSave}
                loading={updateMutation.isPending}
              >
                保存配置
              </Button>
            </div>
          )}
        </Form>
      </Card>
    </div>
  );
}

export default Route;