import { useMemo, memo } from 'react';
import { User, Bot, WifiOff } from 'lucide-react';
import clsx from 'clsx';
import type { Message } from '@/types/chat';
import { formatRelativeTime } from '@/utils/date';
import { ToolCallCard } from './ToolCallCard';

export interface MessageItemProps {
  message: Message;
  isStreaming?: boolean;
  showAvatar?: boolean;
}

function MessageItemComponent({
  message,
  isStreaming = false,
  showAvatar = true,
}: MessageItemProps) {
  const isUser = message.role === 'user';
  const isOffline = message.is_offline;

  // 解析消息内容，提取工具调用等信息
  const { textContent, toolCalls } = useMemo(() => {
    // 简单的内容解析，实际可能需要更复杂的解析逻辑
    if (typeof message.content !== 'string') {
      return { textContent: '', toolCalls: [] };
    }

    return {
      textContent: message.content,
      toolCalls: [],
    };
  }, [message.content]);

  return (
    <div
      className={clsx(
        'flex gap-3 mb-4',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      {showAvatar && (
        <div
          className={clsx(
            'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
          )}
        >
          {isUser ? <User size={18} /> : <Bot size={18} />}
        </div>
      )}

      {/* Message Content */}
      <div
        className={clsx(
          'flex-1 max-w-[80%]',
          isUser ? 'items-end' : 'items-start',
          'flex flex-col gap-2',
          !showAvatar && (isUser ? 'pr-11' : 'pl-11')
        )}
      >
        {/* Timestamp */}
        <div
          className={clsx(
            'text-xs text-gray-400',
            isUser ? 'text-right' : 'text-left'
          )}
        >
          {formatRelativeTime(message.created_at)}
          {isOffline && (
            <span className="ml-2 inline-flex items-center text-amber-500">
              <WifiOff size={12} className="mr-1" />
              离线
            </span>
          )}
        </div>

        {/* Content Bubble */}
        <div
          className={clsx(
            'rounded-lg px-4 py-2',
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100',
            isOffline && 'border border-amber-300'
          )}
        >
          {/* Text Content */}
          {textContent && (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              {textContent}
              {isStreaming && (
                <span className="inline-block w-1 h-4 ml-1 bg-blue-600 animate-pulse" />
              )}
            </div>
          )}

          {/* Tool Calls */}
          {toolCalls.length > 0 && (
            <div className="mt-2 space-y-2">
              {toolCalls.map((tool, index) => (
                <ToolCallCard key={index} toolCall={tool} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export const MessageItem = memo(MessageItemComponent);

export default MessageItem;