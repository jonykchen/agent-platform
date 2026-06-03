import { createFileRoute } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  List,
  Button,
  Empty,
  Typography,
  Tag,
  Badge,
  Tabs,
  Space,
  Popconfirm,
  message,
} from 'antd';
import {
  Bell,
  CheckCircle,
  Trash2,
  Clock,
  ExternalLink,
  AlertCircle,
  Info,
  CheckSquare,
} from 'lucide-react';
import { useState, useMemo } from 'react';
import { useNotificationStore, type Notification } from '@/stores/notificationStore';
import { LoadingState } from '@/components/feedback/LoadingState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { PageLayout } from '@/components/layout/PageLayout';
import { APP_CONFIG } from '@/constants/config';
import { formatRelativeTime, formatDateTime } from '@/utils/date';

const { Title, Text } = Typography;

export const Route = createFileRoute('/notifications/')({
  component: NotificationsPage,
});

// 通知类型配置
const typeConfig: Record<string, { color: string; icon: React.ReactNode }> = {
  approval: { color: 'purple', icon: <CheckSquare className="w-4 h-4" /> },
  system: { color: 'blue', icon: <Info className="w-4 h-4" /> },
  alert: { color: 'orange', icon: <AlertCircle className="w-4 h-4" /> },
  error: { color: 'red', icon: <AlertCircle className="w-4 h-4" /> },
  success: { color: 'green', icon: <CheckCircle className="w-4 h-4" /> },
};

// 优先级配置
const priorityConfig: Record<string, { color: string }> = {
  low: { color: 'default' },
  normal: { color: 'blue' },
  high: { color: 'orange' },
  urgent: { color: 'red' },
};

function NotificationsPage() {
  const queryClient = useQueryClient();

  // 从 store 获取通知
  const {
    notifications,
    unreadCount,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
  } = useNotificationStore();

  // 筛选标签
  const [activeTab, setActiveTab] = useState<'all' | 'unread'>('all');

  // 过滤通知
  const filteredNotifications = useMemo(() => {
    if (activeTab === 'unread') {
      return notifications.filter((n) => !n.read);
    }
    return notifications;
  }, [notifications, activeTab]);

  // 标记已读
  const handleMarkAsRead = (id: string) => {
    markAsRead(id);
  };

  // 标记全部已读
  const handleMarkAllAsRead = () => {
    markAllAsRead();
    message.success('已全部标记为已读');
  };

  // 删除通知
  const handleDelete = (id: string) => {
    removeNotification(id);
    message.success('通知已删除');
  };

  // 清空所有
  const handleClearAll = () => {
    clearAll();
    message.success('通知已清空');
  };

  // 跳转到操作链接
  const handleNavigate = (url: string) => {
    window.location.href = url;
  };

  return (
    <PageLayout>
    <div className="space-y-4">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Title level={4} className="!mb-2">
            通知中心
            {unreadCount > 0 && (
              <Badge count={unreadCount} className="ml-2" />
            )}
          </Title>
          <Text type="secondary">
            查看系统通知和审批提醒
          </Text>
        </div>
        <Space>
          {unreadCount > 0 && (
            <Button onClick={handleMarkAllAsRead}>
              全部标记已读
            </Button>
          )}
          {notifications.length > 0 && (
            <Popconfirm
              title="确定要清空所有通知吗？"
              onConfirm={handleClearAll}
              okText="确定"
              cancelText="取消"
            >
              <Button danger>清空全部</Button>
            </Popconfirm>
          )}
        </Space>
      </div>

      {/* Tabs */}
      <Tabs
        activeKey={activeTab}
        onChange={(key) => setActiveTab(key as 'all' | 'unread')}
        items={[
          {
            key: 'all',
            label: `全部 (${notifications.length})`,
          },
          {
            key: 'unread',
            label: (
              <span>
                未读
                {unreadCount > 0 && (
                  <Badge count={unreadCount} className="ml-2" />
                )}
              </span>
            ),
          },
        ]}
      />

      {/* Notification List */}
      <Card>
        {filteredNotifications.length === 0 ? (
          <EmptyState
            icon={<Bell className="w-12 h-12 text-gray-300" />}
            description={
              activeTab === 'unread' ? '没有未读通知' : '暂无通知'
            }
          />
        ) : (
          <List
            dataSource={filteredNotifications}
            renderItem={(notification) => {
              const typeConf = typeConfig[notification.type] || typeConfig.system;
              const priorityConf = priorityConfig[notification.priority] || priorityConfig.normal;

              return (
                <List.Item
                  className={`cursor-pointer hover:bg-gray-50 transition-colors rounded px-3 -mx-3 ${
                    !notification.read ? 'bg-blue-50' : ''
                  }`}
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    {/* 图标 */}
                    <div
                      className={`p-2 rounded-full bg-${typeConf.color}-100 text-${typeConf.color}-600`}
                    >
                      {typeConf.icon}
                    </div>

                    {/* 内容 */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Text strong={!notification.read}>
                          {notification.title}
                        </Text>
                        <Tag color={priorityConf.color}>{notification.priority}</Tag>
                        {!notification.read && (
                          <span className="w-2 h-2 rounded-full bg-blue-500" />
                        )}
                      </div>
                      <Text type="secondary" className="text-sm block mb-1">
                        {notification.message}
                      </Text>
                      <div className="flex items-center gap-2 text-xs text-gray-400">
                        <Clock className="w-3 h-3" />
                        <span title={formatDateTime(notification.createdAt)}>
                          {formatRelativeTime(notification.createdAt)}
                        </span>
                      </div>
                    </div>

                    {/* 操作 */}
                    <div className="flex items-center gap-1">
                      {notification.actionUrl && (
                        <Button
                          type="link"
                          size="small"
                          icon={<ExternalLink className="w-4 h-4" />}
                          onClick={() => handleNavigate(notification.actionUrl!)}
                        >
                          查看
                        </Button>
                      )}
                      {!notification.read && (
                        <Button
                          type="link"
                          size="small"
                          onClick={() => handleMarkAsRead(notification.id)}
                        >
                          标记已读
                        </Button>
                      )}
                      <Button
                        type="text"
                        size="small"
                        danger
                        icon={<Trash2 className="w-4 h-4" />}
                        onClick={() => handleDelete(notification.id)}
                      />
                    </div>
                  </div>
                </List.Item>
              );
            }}
          />
        )}
      </Card>
    </div>
    </PageLayout>
  );
}

export default Route;
