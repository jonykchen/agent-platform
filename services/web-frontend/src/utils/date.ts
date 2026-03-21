import { format, formatDistanceToNow, parseISO } from 'date-fns';
import { zhCN } from 'date-fns/locale';

/**
 * 格式化日期时间
 */
export function formatDateTime(date: string | Date, formatStr: string = 'yyyy-MM-dd HH:mm:ss'): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, formatStr, { locale: zhCN });
}

/**
 * 格式化日期
 */
export function formatDate(date: string | Date): string {
  return formatDateTime(date, 'yyyy-MM-dd');
}

/**
 * 格式化时间
 */
export function formatTime(date: string | Date): string {
  return formatDateTime(date, 'HH:mm:ss');
}

/**
 * 相对时间（如"3 分钟前"）
 */
export function formatRelativeTime(date: string | Date): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return formatDistanceToNow(d, { addSuffix: true, locale: zhCN });
}

/**
 * 格式化持续时间（毫秒）
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3600000) {
    const minutes = Math.floor(ms / 60000);
    const seconds = Math.floor((ms % 60000) / 1000);
    return `${minutes}m ${seconds}s`;
  }
  const hours = Math.floor(ms / 3600000);
  const minutes = Math.floor((ms % 3600000) / 60000);
  return `${hours}h ${minutes}m`;
}