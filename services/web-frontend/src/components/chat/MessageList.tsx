import { useRef, useCallback, useEffect, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Message } from '@/types/chat';
import { MessageItem } from './MessageItem';
import { APP_CONFIG } from '@/constants/config';

export interface MessageListProps {
  messages: Message[];
  streamingContent?: string;
  streamingRole?: 'user' | 'assistant';
  onLoadMore?: () => void;
  hasMore?: boolean;
  isLoading?: boolean;
}

export function MessageList({
  messages,
  streamingContent,
  streamingRole = 'assistant',
  onLoadMore,
  hasMore = false,
  isLoading = false,
}: MessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  // 合并消息和流式内容
  const displayMessages = useMemo(() => {
    const result = [...messages];
    if (streamingContent && streamingContent.length > 0) {
      result.push({
        id: 'streaming',
        session_id: messages[0]?.session_id || '',
        role: streamingRole,
        content: streamingContent,
        created_at: new Date().toISOString(),
      });
    }
    return result;
  }, [messages, streamingContent, streamingRole]);

  // 虚拟滚动配置
  const rowVirtualizer = useVirtualizer({
    count: displayMessages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => 100, []),
    overscan: APP_CONFIG.VIRTUAL_SCROLL_OVERSCAN,
  });

  // 自动滚动到底部（当有新消息或流式内容更新时）
  useEffect(() => {
    if (parentRef.current && streamingContent) {
      parentRef.current.scrollTop = parentRef.current.scrollHeight;
    }
  }, [streamingContent, displayMessages.length]);

  // 滚动到顶部加载更多
  const handleScroll = useCallback(() => {
    if (!parentRef.current || !hasMore || isLoading) return;

    const { scrollTop, scrollHeight } = parentRef.current;
    // 接近顶部时加载更多
    if (scrollTop < 100) {
      onLoadMore?.();
    }
  }, [hasMore, isLoading, onLoadMore]);

  useEffect(() => {
    const parent = parentRef.current;
    if (parent) {
      parent.addEventListener('scroll', handleScroll);
      return () => parent.removeEventListener('scroll', handleScroll);
    }
  }, [handleScroll]);

  // 初始滚动到底部
  useEffect(() => {
    if (parentRef.current && messages.length > 0) {
      parentRef.current.scrollTop = parentRef.current.scrollHeight;
    }
  }, []); // 只在首次加载时执行

  if (messages.length === 0 && !streamingContent) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <p className="text-lg">开始新的对话</p>
          <p className="text-sm mt-2">输入消息开始与 AI 助手对话</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={parentRef} className="flex-1 overflow-auto px-4 py-6">
      {/* 加载更多指示器 */}
      {hasMore && (
        <div className="flex justify-center py-4">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
        </div>
      )}

      {/* 虚拟列表 */}
      <div
        style={{
          height: rowVirtualizer.getTotalSize(),
          width: '100%',
          position: 'relative',
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const message = displayMessages[virtualRow.index];
          const isStreaming = message.id === 'streaming';
          const prevMessage = virtualRow.index > 0 ? displayMessages[virtualRow.index - 1] : undefined;

          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start}px)`,
              }}
              data-index={virtualRow.index}
              ref={rowVirtualizer.measureElement}
            >
              <MessageItem
                message={message}
                isStreaming={isStreaming}
                showAvatar={!prevMessage || prevMessage.role !== message.role}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default MessageList;