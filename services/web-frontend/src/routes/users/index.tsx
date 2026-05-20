import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import {
  Table,
  Card,
  Button,
  Space,
  Tag,
  Input,
  Modal,
  Form,
  Select,
  message,
  Popconfirm,
  Tooltip,
  Avatar,
  Badge,
} from 'antd';
import {
  Plus,
  Search,
  Edit,
  UserX,
  UserCheck,
  Key,
  RefreshCw,
} from 'lucide-react';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import { PageLayout } from '@/components/layout/PageLayout';
import {
  getUsers,
  createUser,
  updateUser,
  disableUser,
  enableUser,
  resetUserPassword,
  getRoles,
} from '@/services/user';
import type { UserDetail, UserQueryParams, CreateUserRequest, UpdateUserRequest } from '@/services/user';
import type { Role } from '@/types/user';
import { formatDateTime, formatRelativeTime } from '@/utils/date';
import { formatNumber } from '@/utils/format';
import { usePermission, Permissions } from '@/hooks/usePermission';

export const Route = createFileRoute('/users/')({
  component: UsersPage,
});

const statusConfig: Record<string, { color: string; label: string }> = {
  active: { color: 'success', label: '正常' },
  inactive: { color: 'default', label: '未激活' },
  suspended: { color: 'error', label: '已禁用' },
};

const roleColors: Record<Role, string> = {
  admin: 'red',
  operator: 'blue',
  viewer: 'green',
};

function UsersPage() {
  const queryClient = useQueryClient();
  const { hasPermission } = usePermission();

  const [params, setParams] = useState<UserQueryParams>({
    pageNumber: 1,
    pageSize: 20,
  });
  const [editUser, setEditUser] = useState<UserDetail | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createForm] = Form.useForm<CreateUserRequest>();
  const [editForm] = Form.useForm<UpdateUserRequest>();

  // 查询用户列表
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['users', params],
    queryFn: () => getUsers(params),
  });

  // 查询角色列表
  const { data: roles } = useQuery({
    queryKey: ['roles'],
    queryFn: getRoles,
  });

  // 创建用户
  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      message.success('用户创建成功');
      setIsCreateModalOpen(false);
      createForm.resetFields();
    },
    onError: () => {
      message.error('创建失败');
    },
  });

  // 更新用户
  const updateMutation = useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: UpdateUserRequest }) =>
      updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      message.success('用户更新成功');
      setEditUser(null);
      editForm.resetFields();
    },
    onError: () => {
      message.error('更新失败');
    },
  });

  // 禁用用户
  const disableMutation = useMutation({
    mutationFn: disableUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      message.success('用户已禁用');
    },
    onError: () => {
      message.error('操作失败');
    },
  });

  // 启用用户
  const enableMutation = useMutation({
    mutationFn: enableUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      message.success('用户已启用');
    },
    onError: () => {
      message.error('操作失败');
    },
  });

  // 重置密码
  const resetPasswordMutation = useMutation({
    mutationFn: resetUserPassword,
    onSuccess: (data) => {
      Modal.success({
        title: '密码已重置',
        content: (
          <div>
            <p>临时密码:</p>
            <code className="bg-gray-100 px-2 py-1 rounded">{data.temporary_password}</code>
            <p className="mt-2 text-gray-500">请妥善保管，用户首次登录后需要修改密码</p>
          </div>
        ),
      });
    },
    onError: () => {
      message.error('重置密码失败');
    },
  });

  // 分页变化
  const handleTableChange = useCallback((pagination: TablePaginationConfig) => {
    setParams((prev) => ({
      ...prev,
      pageNumber: pagination.current || 1,
      pageSize: pagination.pageSize || 20,
    }));
  }, []);

  // 打开编辑弹窗
  const handleEdit = useCallback((user: UserDetail) => {
    setEditUser(user);
    editForm.setFieldsValue({
      username: user.username,
      email: user.email,
      roles: user.roles,
      status: user.status,
    });
  }, [editForm]);

  // 创建用户
  const handleCreate = useCallback(() => {
    createForm.validateFields().then((values) => {
      createMutation.mutate(values);
    });
  }, [createForm, createMutation]);

  // 更新用户
  const handleUpdate = useCallback(() => {
    if (!editUser) return;
    editForm.validateFields().then((values) => {
      updateMutation.mutate({ userId: editUser.id, data: values });
    });
  }, [editUser, editForm, updateMutation]);

  // 表格列定义
  const columns: ColumnsType<UserDetail> = [
    {
      title: '用户',
      key: 'user',
      width: 200,
      render: (_: unknown, user: UserDetail) => (
        <div className="flex items-center gap-2">
          <Avatar
            style={{ backgroundColor: roleColors[user.roles[0]] || '#1890ff' }}
          >
            {user.username[0].toUpperCase()}
          </Avatar>
          <div>
            <div className="font-medium">{user.username}</div>
            <div className="text-gray-500 text-sm">{user.email}</div>
          </div>
        </div>
      ),
    },
    {
      title: '角色',
      dataIndex: 'roles',
      key: 'roles',
      width: 150,
      render: (roles: Role[]) => (
        <Space>
          {roles.map((role) => (
            <Tag key={role} color={roleColors[role]}>
              {role}
            </Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config = statusConfig[status] || statusConfig.active;
        return <Badge status={config.color as 'success' | 'default' | 'error'} text={config.label} />;
      },
      filters: [
        { text: '正常', value: 'active' },
        { text: '未激活', value: 'inactive' },
        { text: '已禁用', value: 'suspended' },
      ],
    },
    {
      title: '登录次数',
      dataIndex: 'login_count',
      key: 'login_count',
      width: 100,
      render: (count: number) => formatNumber(count),
      sorter: true,
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      width: 150,
      render: (value?: string) =>
        value ? (
          <Tooltip title={formatDateTime(value)}>
            <span>{formatRelativeTime(value)}</span>
          </Tooltip>
        ) : (
          '-'
        ),
      sorter: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 150,
      render: (value: string) => formatDateTime(value),
      sorter: true,
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      render: (_: unknown, user: UserDetail) => (
        <Space>
          <Tooltip title="编辑">
            <Button
              type="text"
              size="small"
              icon={<Edit className="w-4 h-4" />}
              onClick={() => handleEdit(user)}
              disabled={!hasPermission(Permissions.USER_WRITE)}
            />
          </Tooltip>
          {user.status === 'active' ? (
            <Popconfirm
              title="确定要禁用该用户吗？"
              onConfirm={() => disableMutation.mutate(user.id)}
              disabled={!hasPermission(Permissions.USER_WRITE)}
            >
              <Tooltip title="禁用">
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<UserX className="w-4 h-4" />}
                  disabled={!hasPermission(Permissions.USER_WRITE)}
                />
              </Tooltip>
            </Popconfirm>
          ) : (
            <Tooltip title="启用">
              <Button
                type="text"
                size="small"
                icon={<UserCheck className="w-4 h-4" />}
                onClick={() => enableMutation.mutate(user.id)}
                disabled={!hasPermission(Permissions.USER_WRITE)}
              />
            </Tooltip>
          )}
          <Popconfirm
            title="确定要重置该用户的密码吗？"
            onConfirm={() => resetPasswordMutation.mutate(user.id)}
            disabled={!hasPermission(Permissions.USER_WRITE)}
          >
            <Tooltip title="重置密码">
              <Button
                type="text"
                size="small"
                icon={<Key className="w-4 h-4" />}
                disabled={!hasPermission(Permissions.USER_WRITE)}
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <PageLayout>
      <div className="space-y-4">
        {/* 工具栏 */}
        <Card>
          <div className="flex justify-between items-center">
            <Space>
              <Input
                placeholder="搜索用户名"
                prefix={<Search className="w-4 h-4 text-gray-400" />}
                style={{ width: 200 }}
                onChange={(e) =>
                  setParams((prev) => ({ ...prev, username: e.target.value || undefined, pageNumber: 1 }))
                }
              />
              <Input
                placeholder="搜索邮箱"
                prefix={<Search className="w-4 h-4 text-gray-400" />}
                style={{ width: 200 }}
                onChange={(e) =>
                  setParams((prev) => ({ ...prev, email: e.target.value || undefined, pageNumber: 1 }))
                }
              />
              <Select
                placeholder="状态"
                allowClear
                style={{ width: 120 }}
                onChange={(value) =>
                  setParams((prev) => ({ ...prev, status: value, pageNumber: 1 }))
                }
              >
                <Select.Option value="active">正常</Select.Option>
                <Select.Option value="inactive">未激活</Select.Option>
                <Select.Option value="suspended">已禁用</Select.Option>
              </Select>
              <Select
                placeholder="角色"
                allowClear
                style={{ width: 120 }}
                onChange={(value) =>
                  setParams((prev) => ({ ...prev, role: value, pageNumber: 1 }))
                }
              >
                {roles?.map((role) => (
                  <Select.Option key={role.name} value={role.name}>
                    {role.name}
                  </Select.Option>
                ))}
              </Select>
            </Space>
            <Space>
              <Button icon={<RefreshCw className="w-4 h-4" />} onClick={() => refetch()}>
                刷新
              </Button>
              <Button
                type="primary"
                icon={<Plus className="w-4 h-4" />}
                onClick={() => setIsCreateModalOpen(true)}
                disabled={!hasPermission(Permissions.USER_WRITE)}
              >
                创建用户
              </Button>
            </Space>
          </div>
        </Card>

        {/* 表格 */}
        <Card>
          <div className="mb-4">
            共 <span className="font-medium">{formatNumber(data?.total_count || 0)}</span> 个用户
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
              showTotal: (total) => `共 ${formatNumber(total)} 个用户`,
            }}
            onChange={handleTableChange}
          />
        </Card>
      </div>

      {/* 创建用户弹窗 */}
      <Modal
        title="创建用户"
        open={isCreateModalOpen}
        onOk={handleCreate}
        onCancel={() => {
          setIsCreateModalOpen(false);
          createForm.resetFields();
        }}
        confirmLoading={createMutation.isPending}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="password"
            label="初始密码"
            rules={[{ required: true, message: '请输入初始密码' }]}
          >
            <Input.Password />
          </Form.Item>
          <Form.Item
            name="roles"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select mode="multiple">
              {roles?.map((role) => (
                <Select.Option key={role.name} value={role.name}>
                  <Space>
                    <Tag color={roleColors[role.name]}>{role.name}</Tag>
                    <span className="text-gray-500">{role.description}</span>
                  </Space>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑用户弹窗 */}
      <Modal
        title="编辑用户"
        open={!!editUser}
        onOk={handleUpdate}
        onCancel={() => {
          setEditUser(null);
          editForm.resetFields();
        }}
        confirmLoading={updateMutation.isPending}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="username" label="用户名">
            <Input />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input />
          </Form.Item>
          <Form.Item name="roles" label="角色">
            <Select mode="multiple">
              {roles?.map((role) => (
                <Select.Option key={role.name} value={role.name}>
                  <Space>
                    <Tag color={roleColors[role.name]}>{role.name}</Tag>
                    <span className="text-gray-500">{role.description}</span>
                  </Space>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="status" label="状态">
            <Select>
              <Select.Option value="active">正常</Select.Option>
              <Select.Option value="inactive">未激活</Select.Option>
              <Select.Option value="suspended">已禁用</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </PageLayout>
  );
}

export default Route;
