import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Card,
  List,
  Button,
  Input,
  Empty,
  Typography,
  Dropdown,
  Tag,
  Tooltip,
  Space,
  Modal,
  message,
} from 'antd';
import {
  Plus,
  Search,
  MessageSquare,
  MoreVertical,
  Archive,
  Trash2,
  Edit2,
  Clock,
} from 'lucide-react';
import { useState, useMemo } from 'react';
import { sessionService, type SessionListParams } from '@/services/session';
import type { SessionDetail } from '@/services/session';
import { LoadingState } from '@/components/feedback/LoadingState';
import { EmptyState } from '@/components/feedback/EmptyState';
import { APP_CONFIG } from '@/constants/config';
import { ROUTE_PATHS } from '@/constants/routes';
import { formatRelativeTime } from '@/utils/date';

const { Title, Text } = Typography;

export const Route = createFileRoute('/chat/')({
  component: ChatListPage,
});

// 会话状态配置
const statusConfig: Record<string, { color: string; text: string }> = {
  active: { color: 'green', text: '活跃' },
  archived: { color: 'default', text: '已归档' },
  closed: { color: 'default', text: '已关闭' },
};

function ChatListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // 筛选状态
  const [params, setParams] = useState<SessionListParams>({
    status: 'active',
    page: 1,
    pageSize: APP_CONFIG.DEFAULT_PAGE_SIZE,
  });
  const [searchText, setSearchText] = useState('');

  // 获取会话列表
  const {
    data,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['sessions', params],
    queryFn: () => sessionService.list(params),
    staleTime: 60000,
  });

  // 创建会话
  const createMutation = useMutation({
    mutationFn: () => sessionService.create(),
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      navigate({ to: '/chat/$sessionId', params: { sessionId: session.id } });
    },
    onError: () => {
      message.error('创建会话失败');
    },
  });

  // 删除会话
  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => sessionService.delete(sessionId),
    onSuccess: () => {
      message.success('会话已删除');
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
    onError: () => {
      message.error('删除失败');
    },
  });

  // 归档会话
  const archiveMutation = useMutation({
    mutationFn: (sessionId: string) => sessionService.archive(sessionId),
    onSuccess: () => {
      message.success('会话已归档');
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
    },
    onError: () => {
      message.error('归档失败');
    },
  });

  // 编辑标题
  const [editingSession, setEditingSession] = useState<SessionDetail | null>(null);
  const [editTitle, setEditTitle] = useState('');

  const updateTitleMutation = useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: string; title: string }) =>
      sessionService.updateTitle(sessionId, title),
    onSuccess: () => {
      message.success('标题已更新');
      queryClient.invalidateQueries({ queryKey: ['sessions'] });
      setEditingSession(null);
    },
    onError: () => {
      message.error('更新失败');
    },
  });

  // 处理搜索
  const handleSearch = () => {
    setParams((prev) => ({
      ...prev,
      page: 1,
      search: searchText || undefined,
    }));
  };

  // 处理新建会话
  const handleNewChat = () => {
    createMutation.mutate();
  };

  // 处理点击会话
  const handleClickSession = (sessionId: string) => {
    navigate({ to: '/chat/$sessionId', params: { sessionId } });
  };

  // 处理删除
  const handleDelete = (sessionId: string) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后将无法恢复，确定要删除此会话吗？',
      okText: '删除',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => deleteMutation.mutate(sessionId),
    });
  };

  // 处理归档
  const handleArchive = (sessionId: string) => {
    archiveMutation.mutate(sessionId);
  };

  // 处理编辑标题
  const handleEditTitle = (session: SessionDetail) => {
    setEditingSession(session);
    setEditTitle(session.title || '');
  };

  // 处理保存标题
  const handleSaveTitle = () => {
    if (editingSession && editTitle.trim()) {
      updateTitleMutation.mutate({
        sessionId: editingSession.id,
        title: editTitle.trim(),
      });
    }
  };

  // 会话列表
  const sessions = useMemo(() => data?.items || [], [data]);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Title level={4} className="!mb-2">
            对话记录
          </Title>
          <Text type="secondary">
            查看和管理您的对话历史
          </Text>
        </div>
        <Button
          type="primary"
          icon={<Plus className="w-4 h-4" />}
          onClick={handleNewChat}
          loading={createMutation.isPending}
        >
          新建对话
        </Button>
      </div>

      {/* Filters */}
      <Card className="mb-4">
        <Space wrap size="middle">
          <Input.Search
            placeholder="搜索对话"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onSearch={handleSearch}
            style={{ width: 300 }}
            prefix={<Search className="w-4 h-4 text-gray-400" />}
            allowClear
          />
          <Button.Group>
            <Button
              type={params.status === 'active' ? 'primary' : 'default'}
              onClick={() => setParams((p) => ({ ...p, status: 'active', page: 1 }))}
            >
              活跃
            </Button>
            <Button
              type={params.status === 'archived' ? 'primary' : 'default'}
              onClick={() => setParams((p) => ({ ...p, status: 'archived', page: 1 }))}
            >
              已归档
            </Button>
          </Button.Group>
          <Button
            icon={<Search className="w-4 h-4" />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            刷新
          </Button>
        </Space>
      </Card>

      {/* Session List */}
      <Card>
        {isLoading ? (
          <LoadingState />
        ) : sessions.length === 0 ? (
          <EmptyState
            icon={<MessageSquare className="w-12 h-12 text-gray-300" />}
            description={
              params.status === 'archived'
                ? '暂无已归档的对话'
                : '暂无对话记录，开始新对话吧'
            }
            action={
              params.status !== 'archived'
                ? {
                    label: '新建对话',
                    onClick: handleNewChat,
                  }
                : undefined
            }
          />
        ) : (
          <List
            dataSource={sessions}
            renderItem={(session) => {
              const menuItems = [
                {
                  key: 'edit',
                  icon: <Edit2 className="w-4 h-4" />,
                  label: '编辑标题',
                  onClick: () => handleEditTitle(session),
                },
                ...(session.status === 'active'
                  ? [
                      {
                        key: 'archive',
                        icon: <Archive className="w-4 h-4" />,
                        label: '归档',
                        onClick: () => handleArchive(session.id),
                      },
                    ]
                  : []),
                {
                  key: 'delete',
                  icon: <Trash2 className="w-4 h-4" />,
                  label: '删除',
                  danger: true,
                  onClick: () => handleDelete(session.id),
                },
              ];

              return (
                <List.Item
                  className="cursor-pointer hover:bg-gray-50 transition-colors rounded px-2 -mx-2"
                  onClick={() => handleClickSession(session.id)}
                >
                  <div className="flex items-center flex-1 min-w-0">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <Text strong className="truncate">
                          {session.title || '新对话'}
                        </Text>
                        <Tag color={statusConfig[session.status]?.color}>
                          {statusConfig[session.status]?.text}
                        </Tag>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        {session.last_message && (
                          <Text type="secondary" ellipsis className="max-w-xs">
                            {session.last_message}
                          </Text>
                        )}
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {formatRelativeTime(session.updated_at)}
                        </span>
                        <span>消息: {session.messages_count}</span>
                      </div>
                    </div>
                    <Dropdown menu={{ items: menuItems }} trigger={['click']}>
                      <Button
                        type="text"
                        icon={<MoreVertical className="w-4 h-4" />}
                        onClick={(e) => e.stopPropagation()}
                      />
                    </Dropdown>
                  </div>
                </List.Item>
              );
            }}
            pagination={
              data && data.total_count > params.pageSize!
                ? {
                    current: params.page,
                    pageSize: params.pageSize,
                    total: data.total_count,
                    showSizeChanger: true,
                    showTotal: (total) => `共 ${total} 条`,
                    onChange: (page, pageSize) =>
                      setParams((p) => ({ ...p, page, pageSize })),
                  }
                : false
            }
          />
        )}
      </Card>

      {/* Edit Title Modal */}
      <Modal
        title="编辑标题"
        open={!!editingSession}
        onCancel={() => setEditingSession(null)}
        onOk={handleSaveTitle}
        confirmLoading={updateTitleMutation.isPending}
        okText="保存"
        cancelText="取消"
      >
        <Input
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          placeholder="请输入标题"
          maxLength={100}
          showCount
        />
      </Modal>
    </div>
  );
}

export default Route;
