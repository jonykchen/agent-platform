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
  const onLoadMoreRef = useRef(onLoadMore);

  // 每次渲染更新 ref
  onLoadMoreRef.current = onLoadMore;

  // 合并消息和流式内容，按时间排序
  const displayMessages = useMemo(() => {
    // 按创建时间排序消息
    const sorted = [...messages].sort((a, b) =>
      new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );

    if (streamingContent && streamingContent.length > 0) {
      sorted.push({
        id: 'streaming',
        session_id: messages[0]?.session_id || '',
        role: streamingRole,
        content: streamingContent,
        created_at: new Date().toISOString(),
      });
    }
    return sorted;
  }, [messages, streamingContent, streamingRole]);

  // 虚拟滚动配置
  const rowVirtualizer = useVirtualizer({
    count: displayMessages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: useCallback(() => 100, []),
    overscan: APP_CONFIG.VIRTUAL_SCROLL_OVERSCAN,
  });

  // 自动滚动到底部（仅在用户已处于底部附近时）
  useEffect(() => {
    const parent = parentRef.current;
    if (!parent || !streamingContent) return;

    // 计算用户是否在底部附近（距离底部 100px 以内）
    const isNearBottom = parent.scrollHeight - parent.scrollTop - parent.clientHeight < 100;
    if (isNearBottom) {
      parent.scrollTop = parent.scrollHeight;
    }
  }, [streamingContent, displayMessages.length]);

  // 滚动到顶部加载更多 - 使用 ref 避免依赖变化
  useEffect(() => {
    const parent = parentRef.current;
    if (!parent) return;

    const handleScroll = () => {
      if (!hasMore || isLoading) return;
      const { scrollTop } = parent;
      if (scrollTop < 100) {
        onLoadMoreRef.current?.();
      }
    };

    parent.addEventListener('scroll', handleScroll);
    return () => parent.removeEventListener('scroll', handleScroll);
  }, [hasMore, isLoading]);

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