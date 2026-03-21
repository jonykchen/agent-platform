import { createFileRoute } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag, Space, Typography, Collapse, Divider, Empty } from 'antd';
import { Shield, Key, Lock } from 'lucide-react';
import type { ColumnsType } from 'antd/es/table';
import { PageLayout } from '@/components/layout/PageLayout';
import { getRoles, getPermissions } from '@/services/user';
import type { Role } from '@/types/user';

const { Title, Text } = Typography;
const { Panel } = Collapse;

export const Route = createFileRoute('/users/roles')({
  component: RolesPage,
});

const roleColors: Record<Role, string> = {
  admin: 'red',
  operator: 'blue',
  viewer: 'green',
};

const roleDescriptions: Record<Role, string> = {
  admin: '系统管理员，拥有所有权限',
  operator: '运维人员，可以执行日常操作和审批',
  viewer: '查看者，只能查看数据，无法修改',
};

const categoryLabels: Record<string, string> = {
  chat: '对话',
  approval: '审批',
  tool: '工具',
  audit: '审计',
  tenant: '租户',
  user: '用户',
  dashboard: '监控',
};

function RolesPage() {
  // 查询角色列表
  const { data: roles, isLoading: rolesLoading } = useQuery({
    queryKey: ['roles'],
    queryFn: getRoles,
  });

  // 查询权限列表
  const { data: permissions, isLoading: permissionsLoading } = useQuery({
    queryKey: ['permissions'],
    queryFn: getPermissions,
  });

  // 按分类分组权限
  const permissionsByCategory = permissions?.reduce(
    (acc, perm) => {
      const category = perm.category || 'other';
      if (!acc[category]) {
        acc[category] = [];
      }
      acc[category].push(perm);
      return acc;
    },
    {} as Record<string, typeof permissions>
  );

  return (
    <PageLayout>
      <div className="space-y-4">
        <Title level={4}>
          <Shield className="w-5 h-5 inline mr-2" />
          角色权限管理
        </Title>

        {/* 角色权限表格 */}
        <Card title="角色权限映射" loading={rolesLoading}>
          <Table
            dataSource={roles}
            rowKey="name"
            pagination={false}
            columns={[
              {
                title: '角色',
                dataIndex: 'name',
                key: 'name',
                width: 120,
                render: (name: Role) => (
                  <Tag color={roleColors[name]} className="text-base px-3 py-1">
                    {name}
                  </Tag>
                ),
              },
              {
                title: '描述',
                dataIndex: 'description',
                key: 'description',
                width: 200,
                render: (desc: string, record) => (
                  <span>
                    {desc}
                    {record.name && (
                      <div className="text-gray-500 text-sm mt-1">
                        {roleDescriptions[record.name]}
                      </div>
                    )}
                  </span>
                ),
              },
              {
                title: '权限数量',
                key: 'permission_count',
                width: 100,
                render: (_: unknown, record: { permissions: string[] }) => (
                  <Tag>{record.permissions?.length || 0}</Tag>
                ),
              },
              {
                title: '权限列表',
                dataIndex: 'permissions',
                key: 'permissions',
                render: (permissions: string[]) => (
                  <Space wrap>
                    {permissions?.map((perm) => {
                      const [category] = perm.split(':');
                      return (
                        <Tag key={perm} color="default">
                          {perm}
                        </Tag>
                      );
                    })}
                  </Space>
                ),
              },
            ]}
          />
        </Card>

        {/* 权限详情 */}
        <Card title="权限详情" loading={permissionsLoading}>
          {permissionsByCategory ? (
            <Collapse defaultActiveKey={Object.keys(permissionsByCategory)}>
              {Object.entries(permissionsByCategory).map(([category, perms]) => (
                <Panel
                  header={
                    <Space>
                      <Lock className="w-4 h-4" />
                      <span className="font-medium">
                        {categoryLabels[category] || category}
                      </span>
                      <Tag>{perms.length}</Tag>
                    </Space>
                  }
                  key={category}
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {perms.map((perm) => (
                      <div
                        key={perm.name}
                        className="border rounded p-3 bg-gray-50"
                      >
                        <div className="flex items-center gap-2 mb-2">
                          <Key className="w-4 h-4 text-blue-500" />
                          <Text code className="font-mono">
                            {perm.name}
                          </Text>
                        </div>
                        <Text type="secondary">{perm.description}</Text>
                      </div>
                    ))}
                  </div>
                </Panel>
              ))}
            </Collapse>
          ) : (
            <Empty description="暂无权限数据" />
          )}
        </Card>
      </div>
    </PageLayout>
  );
}

export default Route;
