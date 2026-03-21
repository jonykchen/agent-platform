import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import {
  Card,
  Form,
  Input,
  Select,
  InputNumber,
  Button,
  Space,
  message,
  Typography,
  Divider,
  Row,
  Col,
  Checkbox,
} from 'antd';
import {
  SaveOutlined,
  ArrowLeftOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { registerTool } from '@/services/tools';
import { usePermission } from '@/hooks/usePermission';
import { ROUTES } from '@/constants/routes';
import type { ToolRegisterRequest, JSONSchema } from '@/types/tools';

export const Route = createFileRoute('/tools/register')();

const { TextArea } = Input;
const { Text } = Typography;

/** 默认 JSON Schema */
const DEFAULT_SCHEMA: JSONSchema = {
  type: 'object',
  properties: {},
  required: [],
};

export default function ToolRegisterPage() {
  const navigate = useNavigate();
  const { isAdmin, hasPermission } = usePermission();
  const [form] = Form.useForm<ToolRegisterRequest>();
  const [schemaText, setSchemaText] = useState(JSON.stringify(DEFAULT_SCHEMA, null, 2));
  const [schemaError, setSchemaError] = useState<string | null>(null);

  // 权限检查
  const canRegister = isAdmin || hasPermission('tool:write');

  // 注册 Mutation
  const registerMutation = useMutation({
    mutationFn: registerTool,
    onSuccess: (data) => {
      message.success('工具注册成功');
      navigate({ to: ROUTES.TOOLS_DETAIL, params: { name: data.name } });
    },
    onError: (error: unknown) => {
      message.error('工具注册失败');
      console.error('Register tool error:', error);
    },
  });

  // 解析 JSON Schema
  const parseSchema = (text: string): JSONSchema | null => {
    try {
      const parsed = JSON.parse(text);
      setSchemaError(null);
      return parsed;
    } catch {
      setSchemaError('JSON 格式无效');
      return null;
    }
  };

  // 提交表单
  const handleSubmit = async (values: ToolRegisterRequest) => {
    const schema = parseSchema(schemaText);
    if (!schema) {
      message.error('参数 Schema 格式错误');
      return;
    }

    const payload: ToolRegisterRequest = {
      ...values,
      parameters: schema,
      tags: values.tags?.filter(Boolean) ?? [],
    };

    registerMutation.mutate(payload);
  };

  if (!canRegister) {
    return (
      <Card>
        <div className="flex flex-col items-center justify-center py-12">
          <ExclamationCircleOutlined style={{ fontSize: 48, color: '#faad14' }} />
          <Text className="mt-4 text-lg">您没有权限注册工具</Text>
          <Button type="link" onClick={() => navigate({ to: ROUTES.TOOLS })}>
            返回工具列表
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center mb-4">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate({ to: ROUTES.TOOLS })}
          >
            返回
          </Button>
          <Text strong style={{ fontSize: 18, marginLeft: 16 }}>
            注册工具
          </Text>
        </div>

        <Divider />

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          initialValues={{
            version: '1.0.0',
            category: 'query',
            risk_level: 'low',
            method: 'POST',
            auth_type: 'service_token',
            timeout_ms: 15000,
            allowed_roles: ['admin', 'operator'],
            enabled: true,
          }}
        >
          {/* 基本信息 */}
          <Typography.Title level={5}>基本信息</Typography.Title>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="工具名称"
                rules={[
                  { required: true, message: '请输入工具名称' },
                  {
                    pattern: /^[a-z][a-z0-9_]*$/,
                    message: '只能包含小写字母、数字和下划线，且以字母开头',
                  },
                ]}
              >
                <Input placeholder="例如: query_order_status" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="version"
                label="版本"
                rules={[{ required: true, message: '请输入版本号' }]}
              >
                <Input placeholder="例如: 1.0.0" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="description"
            label="描述"
            rules={[{ required: true, message: '请输入工具描述' }]}
          >
            <TextArea
              rows={2}
              placeholder="描述工具的功能和用途"
              showCount
              maxLength={500}
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item
                name="category"
                label="类型"
                rules={[{ required: true, message: '请选择类型' }]}
              >
                <Select
                  options={[
                    { value: 'query', label: '查询 (只读)' },
                    { value: 'write', label: '写入 (产生变更)' },
                    { value: 'external', label: '外部 (第三方)' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="risk_level"
                label="风险等级"
                rules={[{ required: true, message: '请选择风险等级' }]}
              >
                <Select
                  options={[
                    { value: 'low', label: '低风险' },
                    { value: 'medium', label: '中风险' },
                    { value: 'high', label: '高风险' },
                    { value: 'critical', label: '严重风险' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="owner_team" label="所属团队">
                <Input placeholder="例如: order-team" />
              </Form.Item>
            </Col>
          </Row>

          <Divider />

          {/* 端点配置 */}
          <Typography.Title level={5}>端点配置</Typography.Title>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="endpoint"
                label="端点 URL"
                rules={[
                  { required: true, message: '请输入端点 URL' },
                  { type: 'url', message: '请输入有效的 URL' },
                ]}
              >
                <Input placeholder="例如: https://api.example.com/orders" />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item
                name="method"
                label="HTTP 方法"
                rules={[{ required: true, message: '请选择方法' }]}
              >
                <Select
                  options={[
                    { value: 'GET', label: 'GET' },
                    { value: 'POST', label: 'POST' },
                    { value: 'PUT', label: 'PUT' },
                    { value: 'DELETE', label: 'DELETE' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item
                name="timeout_ms"
                label="超时时间 (ms)"
                rules={[{ required: true, message: '请输入超时时间' }]}
              >
                <InputNumber min={1000} max={120000} step={1000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="auth_type"
            label="认证类型"
            rules={[{ required: true, message: '请选择认证类型' }]}
          >
            <Select
              options={[
                { value: 'service_token', label: '服务令牌' },
                { value: 'oauth2', label: 'OAuth 2.0' },
                { value: 'api_key', label: 'API Key' },
                { value: 'none', label: '无认证' },
              ]}
            />
          </Form.Item>

          <Divider />

          {/* 参数定义 */}
          <Typography.Title level={5}>参数定义 (JSON Schema)</Typography.Title>
          <Form.Item
            label="参数 Schema"
            validateStatus={schemaError ? 'error' : ''}
            help={schemaError}
          >
            <TextArea
              rows={12}
              value={schemaText}
              onChange={(e) => setSchemaText(e.target.value)}
              style={{ fontFamily: 'monospace' }}
              placeholder="输入 JSON Schema 定义工具参数"
            />
          </Form.Item>

          <Divider />

          {/* 权限和配额 */}
          <Typography.Title level={5}>权限与配额</Typography.Title>
          <Form.Item
            name="allowed_roles"
            label="允许角色"
            rules={[{ required: true, message: '请选择允许的角色' }]}
          >
            <Checkbox.Group
              options={[
                { value: 'admin', label: '管理员 (admin)' },
                { value: 'operator', label: '操作员 (operator)' },
                { value: 'viewer', label: '查看者 (viewer)' },
              ]}
            />
          </Form.Item>

          <Form.Item name="daily_quota_per_user" label="每用户每日配额">
            <InputNumber
              min={0}
              placeholder="不限制请留空"
              style={{ width: 200 }}
            />
          </Form.Item>

          <Form.Item name="tags" label="标签">
            <Select
              mode="tags"
              placeholder="输入标签，回车添加"
              options={[]}
            />
          </Form.Item>

          <Form.Item name="enabled" label="启用状态" valuePropName="checked">
            <Checkbox>注册后立即启用</Checkbox>
          </Form.Item>

          <Divider />

          {/* 提交按钮 */}
          <Form.Item>
            <Space>
              <Button
                type="primary"
                htmlType="submit"
                icon={<SaveOutlined />}
                loading={registerMutation.isPending}
              >
                注册工具
              </Button>
              <Button onClick={() => navigate({ to: ROUTES.TOOLS })}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
