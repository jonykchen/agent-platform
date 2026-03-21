import { Dropdown, Avatar, Badge, Button, Space } from 'antd';
import { UserOutlined, LogoutOutlined, BellOutlined, SettingOutlined } from '@ant-design/icons';
import { useAuth } from '@/hooks/useAuth';
import { useNotificationStore } from '@/stores/notificationStore';
import { useNavigate } from '@tanstack/react-router';
import type { MenuProps } from 'antd';

export function Header() {
  const { user, tenant, logout } = useAuth();
  const unreadCount = useNotificationStore((state) => state.unreadCount);
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
  };

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人设置',
      onClick: () => navigate({ to: '/users' }),
    },
    {
      key: 'tenant',
      icon: <SettingOutlined />,
      label: '租户配置',
      onClick: () => navigate({ to: '/tenant' }),
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
      danger: true,
    },
  ];

  return (
    <header className="h-16 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between px-6">
      {/* Logo */}
      <div className="flex items-center gap-3">
        <img src="/logo.svg" alt="Logo" className="h-8 w-8" />
        <span className="font-semibold text-lg text-gray-900 dark:text-white">
          Agent Platform
        </span>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-4">
        {/* Tenant info */}
        {tenant && (
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {tenant.name}
            <span className="ml-2 px-2 py-0.5 bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 rounded text-xs">
              {tenant.tier}
            </span>
          </div>
        )}

        {/* Notifications */}
        <Button
          type="text"
          icon={
            <Badge count={unreadCount} size="small">
              <BellOutlined className="text-gray-600 dark:text-gray-300" />
            </Badge>
          }
          onClick={() => navigate({ to: '/notifications' })}
        />

        {/* User dropdown */}
        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <div className="flex items-center gap-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 px-3 py-1.5 rounded-lg">
            <Avatar
              size="small"
              icon={<UserOutlined />}
              className="bg-blue-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-200">
              {user?.username}
            </span>
          </div>
        </Dropdown>
      </div>
    </header>
  );
}

export default Header;