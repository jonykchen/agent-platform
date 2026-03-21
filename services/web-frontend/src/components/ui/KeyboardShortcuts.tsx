import { useEffect, useCallback } from 'react';
import { message } from 'antd';

export interface KeyboardShortcutsConfig {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
  action: () => void;
  description?: string;
  preventDefault?: boolean;
}

export interface KeyboardShortcutsProps {
  shortcuts: KeyboardShortcutsConfig[];
  enabled?: boolean;
}

export function useKeyboardShortcuts(shortcuts: KeyboardShortcutsConfig[], enabled = true) {
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (!enabled) return;

      // 忽略输入框中的快捷键
      const target = event.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
        // 只允许 Escape 和特定快捷键
        if (event.key !== 'Escape') {
          return;
        }
      }

      for (const shortcut of shortcuts) {
        const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
        const ctrlMatch = shortcut.ctrl ? event.ctrlKey : !event.ctrlKey;
        const metaMatch = shortcut.meta ? event.metaKey : !event.metaKey;
        const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
        const altMatch = shortcut.alt ? event.altKey : !event.altKey;

        if (keyMatch && ctrlMatch && metaMatch && shiftMatch && altMatch) {
          if (shortcut.preventDefault !== false) {
            event.preventDefault();
          }
          shortcut.action();
          return;
        }
      }
    },
    [shortcuts, enabled]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const showShortcutsHelp = useCallback(() => {
    const shortcutList = shortcuts
      .filter((s) => s.description)
      .map((s) => {
        const keys = [];
        if (s.ctrl) keys.push('Ctrl');
        if (s.meta) keys.push('⌘');
        if (s.alt) keys.push('Alt');
        if (s.shift) keys.push('Shift');
        keys.push(s.key.toUpperCase());
        return `${keys.join(' + ')}: ${s.description}`;
      })
      .join('\n');

    message.info({
      content: (
        <div className="whitespace-pre-line">
          <div className="font-bold mb-2">快捷键</div>
          {shortcutList}
        </div>
      ),
      duration: 5,
    });
  }, [shortcuts]);

  return { showShortcutsHelp };
}

export function KeyboardShortcuts({ shortcuts, enabled = true }: KeyboardShortcutsProps) {
  useKeyboardShortcuts(shortcuts, enabled);
  return null;
}

// 预定义的常用快捷键配置
export const CommonShortcuts = {
  search: (onSearch: () => void): KeyboardShortcutsConfig => ({
    key: 'k',
    ctrl: true,
    action: onSearch,
    description: '搜索',
  }),
  newChat: (onNew: () => void): KeyboardShortcutsConfig => ({
    key: 'n',
    ctrl: true,
    action: onNew,
    description: '新建对话',
  }),
  save: (onSave: () => void): KeyboardShortcutsConfig => ({
    key: 's',
    ctrl: true,
    action: onSave,
    description: '保存',
  }),
  escape: (onEscape: () => void): KeyboardShortcutsConfig => ({
    key: 'Escape',
    action: onEscape,
    description: '关闭/取消',
  }),
  help: (onHelp: () => void): KeyboardShortcutsConfig => ({
    key: '/',
    action: onHelp,
    description: '显示帮助',
  }),
};

export default KeyboardShortcuts;
