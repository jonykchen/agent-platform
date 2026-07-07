import { createFileRoute, useNavigate, useSearch } from '@tanstack/react-router';
import { useState } from 'react';
import { Form, Input, Button, Card, message, Alert } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuth } from '@/hooks/useAuth';
import type { LoginRequest } from '@/types/user';

export const Route = createFileRoute('/login')({
  component: LoginPage,
});

interface LoginSearch {
  redirect?: string;
}

function LoginPage() {
  const navigate = useNavigate();
  const search = useSearch({ from: '/login' }) as LoginSearch;
  const { login, isLoading } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (values: LoginRequest) => {
    setError(null);
    try {
      await login(values);
      message.success('登录成功');
      // 跳转到之前的页面或首页
      navigate({ to: search.redirect || '/' });
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : '登录失败，请检查用户名和密码';
      setError(errorMsg);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <Card className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-gray-900">Agent Platform</h1>
          <p className="text-gray-500 mt-2">企业级 AI Agent 平台</p>
        </div>

        {error && (
          <Alert
            message="登录失败"
            description={error}
            type="error"
            showIcon
            className="mb-4"
          />
        )}

        <Form
          name="login"
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
              autoComplete="current-password"
            />
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={isLoading}
              block
            >
              登录
            </Button>
          </Form.Item>
        </Form>

        <div className="text-center text-sm text-gray-500">
          <p>测试账号：admin / admin123</p>
          <p>其他：operator / operator123 | viewer / viewer123</p>
        </div>
      </Card>
    </div>
  );
}

export default LoginPage;