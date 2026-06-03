import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import {
  Card,
  Button,
  Typography,
  Dropdown,
  message,
} from 'antd';
import {
  ArrowLeft,
  Archive,
  Trash2,
  StopCircle,
  RotateCcw,
  MoreVertical,
} from 'lucide-react';
import { useState, useCallback } from 'react';
import { sessionService } from '@/services/session';
import { useChat } from '@/hooks/useChat';
import { MessageList, InputBox, StepVisualizer } from '@/components/chat';
import { LoadingState } from '@/components/feedback/LoadingState';
import { PageLayout } from '@/components/layout/PageLayout';

const { Title, Text } = Typography;

export const Route = createFileRoute('/chat/$sessionId')({
  component: ChatDetailPage,
});

function ChatDetailPage() {
  const { sessionId } = Route.useParams();
  const navigate = useNavigate();

  // 获取会话信息
  const { data: session, isLoading: sessionLoading } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => sessionService.get(sessionId),
    staleTime: 60000,
  });

  // Chat hook
  const {
    messages,
    isStreaming,
    streamingContent,
    currentSteps,
    sendMessage,
    cancel,
    retry,
    clearMessages,
    isOffline,
  } = useChat({
    sessionId,
    onComplete: (msg) => {
      // 消息完成后的处理
    },
    onError: (error) => {
      message.error(`发送失败: ${error.message}`);
    },
  });

  // 输入框状态
  const [inputValue, setInputValue] = useState('');

  // 发送消息
  const handleSend = useCallback(
    (content: string) => {
      if (!content.trim()) return;
      sendMessage({ content });
      setInputValue('');
    },
    [sendMessage]
  );

  // 处理取消
  const handleCancel = useCallback(() => {
    cancel();
    message.info('已取消');
  }, [cancel]);

  // 处理重试
  const handleRetry = useCallback(() => {
    retry();
  }, [retry]);

  // 处理返回
  const handleBack = () => {
    navigate({ to: '/chat' });
  };

  // 处理归档
  const handleArchive = async () => {
    try {
      await sessionService.archive(sessionId);
      message.success('会话已归档');
      navigate({ to: '/chat' });
    } catch {
      message.error('归档失败');
    }
  };

  // 处理删除
  const handleDelete = async () => {
    try {
      await sessionService.delete(sessionId);
      message.success('会话已删除');
      navigate({ to: '/chat' });
    } catch {
      message.error('删除失败');
    }
  };

  // 更多操作菜单
  const moreMenuItems = [
    {
      key: 'archive',
      icon: <Archive className="w-4 h-4" />,
      label: '归档会话',
      onClick: handleArchive,
    },
    {
      key: 'clear',
      icon: <Trash2 className="w-4 h-4" />,
      label: '清空消息',
      onClick: () => {
        clearMessages();
        message.success('消息已清空');
      },
    },
    {
      key: 'delete',
      icon: <Trash2 className="w-4 h-4" />,
      label: '删除会话',
      danger: true,
      onClick: handleDelete,
    },
  ];

  if (sessionLoading) {
    return <PageLayout><LoadingState /></PageLayout>;
  }

  // 过滤掉 undefined 的步骤
  const validSteps = currentSteps.filter((step): step is NonNullable<typeof step> => step !== undefined);

  return (
    <PageLayout>
    <div className="flex flex-col h-[calc(100vh-120px)] bg-gray-50 -m-6">
      {/* Header */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button
            type="text"
            icon={<ArrowLeft className="w-5 h-5" />}
            onClick={handleBack}
          />
          <div>
            <Title level={5} className="!mb-0">
              {session?.title || '对话'}
            </Title>
            {isOffline && (
              <Text type="warning" className="text-xs">
                离线模式
              </Text>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isStreaming && (
            <Button
              danger
              icon={<StopCircle className="w-4 h-4" />}
              onClick={handleCancel}
            >
              停止
            </Button>
          )}
          <Dropdown menu={{ items: moreMenuItems }} trigger={['click']}>
            <Button type="text" icon={<MoreVertical className="w-5 h-5" />} />
          </Dropdown>
        </div>
      </div>

      {/* 步骤可视化 - 思考过程 */}
      {validSteps.length > 0 && (
        <div className="bg-blue-50 border-b px-4 py-2 max-h-48 overflow-y-auto">
          <StepVisualizer steps={validSteps} />
        </div>
      )}

      {/* 消息列表 */}
      <div className="flex-1 overflow-hidden">
        <Card className="h-full flex flex-col" styles={{ body: { flex: 1, display: 'flex', flexDirection: 'column', padding: 0 } }}>
          <MessageList
            messages={messages}
            streamingContent={streamingContent}
            streamingRole="assistant"
          />
        </Card>
      </div>

      {/* 输入区域 */}
      <div className="bg-white border-t">
        <InputBox
          value={inputValue}
          onChange={setInputValue}
          onSend={handleSend}
          disabled={isStreaming}
          isStreaming={isStreaming}
          placeholder="输入消息..."
          onCancel={handleCancel}
        />
        {!isStreaming && messages.length > 0 && (
          <div className="mt-2 flex justify-center pb-2">
            <Button
              type="link"
              size="small"
              icon={<RotateCcw className="w-4 h-4" />}
              onClick={handleRetry}
            >
              重试上一条
            </Button>
          </div>
        )}
      </div>
    </div>
    </PageLayout>
  );
}

export default Route;
