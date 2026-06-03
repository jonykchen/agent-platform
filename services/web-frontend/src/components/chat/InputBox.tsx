import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, StopCircle, Loader2 } from 'lucide-react';
import { Button } from 'antd';
import clsx from 'clsx';
import { APP_CONFIG } from '@/constants/config';

export interface InputBoxProps {
  onSend: (message: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  isStreaming?: boolean;
  placeholder?: string;
  maxRows?: number;
  value?: string;
  onChange?: (value: string) => void;
}

export function InputBox({
  onSend,
  onCancel,
  disabled = false,
  isStreaming = false,
  placeholder = '输入消息...',
  maxRows = 6,
  value: controlledValue,
  onChange: controlledOnChange,
}: InputBoxProps) {
  const [internalValue, setInternalValue] = useState('');

  // Use controlled value if provided, otherwise use internal state
  const value = controlledValue !== undefined ? controlledValue : internalValue;
  const setValue = controlledOnChange || setInternalValue;
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 使用 ref 存储回调，避免依赖变化
  const onSendRef = useRef(onSend);
  const onCancelRef = useRef(onCancel);
  onSendRef.current = onSend;
  onCancelRef.current = onCancel;

  // 自动调整高度
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.style.height = 'auto';
    const lineHeight = parseInt(getComputedStyle(textarea).lineHeight);
    const maxHeight = lineHeight * maxRows;
    const scrollHeight = Math.min(textarea.scrollHeight, maxHeight);
    textarea.style.height = `${scrollHeight}px`;
  }, [maxRows]);

  // 监听输入变化调整高度
  useEffect(() => {
    adjustHeight();
  }, [value, adjustHeight]);

  // 发送消息 - 使用 ref 避免依赖变化
  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled || isStreaming) return;

    if (trimmed.length > APP_CONFIG.MAX_MESSAGE_LENGTH) {
      return;
    }

    onSendRef.current(trimmed);
    setValue('');
  }, [value, disabled, isStreaming, setValue]);

  // 键盘快捷键
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter 发送（不含 Shift）
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // 取消操作
  const handleCancel = useCallback(() => {
    onCancelRef.current?.();
  }, []);

  const canSend = value.trim().length > 0 && !disabled && !isStreaming;

  return (
    <div className="border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="relative flex items-end gap-2">
          {/* 输入框 */}
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className={clsx(
              'flex-1 resize-none rounded-lg border border-gray-300 dark:border-gray-600',
              'bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100',
              'px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500',
              'placeholder:text-gray-400 dark:placeholder:text-gray-500',
              'transition-all duration-200',
              disabled && 'opacity-50 cursor-not-allowed'
            )}
            style={{ minHeight: '44px', maxHeight: `${maxRows * 24}px` }}
          />

          {/* 发送/取消按钮 */}
          {isStreaming ? (
            <Button
              type="default"
              danger
              icon={<StopCircle size={18} />}
              onClick={handleCancel}
              className="flex-shrink-0"
            >
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              icon={disabled ? <Loader2 className="animate-spin" size={18} /> : <Send size={18} />}
              onClick={handleSend}
              disabled={!canSend}
              className="flex-shrink-0"
            >
              发送
            </Button>
          )}
        </div>

        {/* 字数统计 */}
        <div className="mt-1 text-xs text-gray-400 text-right">
          {value.length} / {APP_CONFIG.MAX_MESSAGE_LENGTH}
        </div>
      </div>
    </div>
  );
}

export default InputBox;