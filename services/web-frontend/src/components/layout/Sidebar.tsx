import { Layout, Menu } from 'antd';
import {
  MessageSquare,
  CheckSquare,
  Wrench,
  FileSearch,
  BarChart2,
  Users,
  Settings,
  Database,
  Bell,
} from 'lucide-react';
import { useLocation, useNavigate } from '@tanstack/react-router';
import { usePermission, Permissions } from '@/hooks/usePermission';
import { useUIStore } from '@/stores/uiStore';
import type { MenuProps } from 'antd';

const { Sider } = Layout;

interface MenuItem {
  key: string;
  icon?: React.ReactNode;
  label: string;
  permission?: string;
  type?: 'item' | 'divider';
}

const menuItems: MenuItem[] = [
  {
    key: '/chat',
    icon: <MessageSquare className="w-4 h-4" />,
    label: '对话',
    permission: Permissions.CHAT_READ,
  },
  {
    key: '/approval',
    icon: <CheckSquare className="w-4 h-4" />,
    label: '审批中心',
    permission: Permissions.APPROVAL_READ,
  },
  {
    key: '/tools',
    icon: <Wrench className="w-4 h-4" />,
    label: '工具管理',
    permission: Permissions.TOOL_READ,
  },
  {
    key: '/audit',
    icon: <FileSearch className="w-4 h-4" />,
    label: '审计日志',
    permission: Permissions.AUDIT_READ,
  },
  {
    key: '/dashboard',
    icon: <BarChart2 className="w-4 h-4" />,
    label: '监控面板',
    permission: Permissions.DASHBOARD_READ,
  },
  {
    key: '/knowledge',
    icon: <Database className="w-4 h-4" />,
    label: '知识库',
    permission: Permissions.KNOWLEDGE_READ,
  },
  {
    key: '/notifications',
    icon: <Bell className="w-4 h-4" />,
    label: '通知中心',
    permission: Permissions.CHAT_READ,
  },
  {
    key: 'divider-1',
    type: 'divider',
  } as MenuItem,
  {
    key: '/users',
    icon: <Users className="w-4 h-4" />,
    label: '用户管理',
    permission: Permissions.USER_READ,
  },
  {
    key: '/tenant',
    icon: <Settings className="w-4 h-4" />,
    label: '租户配置',
    permission: Permissions.TENANT_READ,
  },
];

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { hasPermission } = usePermission();
  const { sidebarCollapsed, toggleSidebar } = useUIStore();

  // 过滤有权限的菜单并转换为 Ant Design 格式
  const filteredItems: MenuProps['items'] = menuItems
    .filter((item) => {
      if (item.type === 'divider') return true;
      return !item.permission || hasPermission(item.permission);
    })
    .map((item) => {
      if (item.type === 'divider') {
        return { type: 'divider' as const, key: item.key };
      }
      return {
        key: item.key,
        icon: item.icon,
        label: item.label,
      };
    });

  // 获取当前选中的菜单项
  const selectedKey = '/' + location.pathname.split('/')[1];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (!key.startsWith('divider')) {
      navigate({ to: key });
    }
  };

  return (
    <Sider
      collapsible
      collapsed={sidebarCollapsed}
      onCollapse={toggleSidebar}
      className="bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700"
      theme="light"
      width={220}
      collapsedWidth={64}
    >
      <Menu
        mode="inline"
        selectedKeys={[selectedKey]}
        onClick={handleMenuClick}
        items={filteredItems}
        className="border-none h-full"
      />
    </Sider>
  );
}

export default Sidebar;