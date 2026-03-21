import { memo } from 'react';
import { Wrench, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import clsx from 'clsx';

export interface ToolCallData {
  name: string;
  arguments?: Record<string, unknown>;
  result?: unknown;
  status: 'pending' | 'running' | 'success' | 'error';
  error?: string;
  duration?: number;
}

export interface ToolCallCardProps {
  toolCall: ToolCallData;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

function ToolCallCardComponent({
  toolCall,
  collapsed = false,
  onToggleCollapse,
}: ToolCallCardProps) {
  const { name, arguments: args, result, status, error, duration } = toolCall;

  const statusColors = {
    pending: 'bg-gray-100 dark:bg-gray-700 border-gray-300 dark:border-gray-600',
    running: 'bg-blue-50 dark:bg-blue-900/30 border-blue-300 dark:border-blue-600',
    success: 'bg-green-50 dark:bg-green-900/30 border-green-300 dark:border-green-600',
    error: 'bg-red-50 dark:bg-red-900/30 border-red-300 dark:border-red-600',
  };

  const iconColors = {
    pending: 'text-gray-400',
    running: 'text-blue-600 animate-spin',
    success: 'text-green-600',
    error: 'text-red-600',
  };

  return (
    <div
      className={clsx(
        'rounded-lg border px-3 py-2 text-sm',
        statusColors[status]
      )}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={onToggleCollapse}
      >
        {/* Status Icon */}
        {status === 'running' ? (
          <Loader2 size={14} className={iconColors[status]} />
        ) : status === 'success' ? (
          <CheckCircle2 size={14} className={iconColors[status]} />
        ) : status === 'error' ? (
          <AlertCircle size={14} className={iconColors[status]} />
        ) : (
          <Wrench size={14} className={iconColors[status]} />
        )}

        {/* Tool Name */}
        <span className="font-medium">{name}</span>

        {/* Duration */}
        {duration !== undefined && (
          <span className="text-xs text-gray-400 ml-auto">
            {duration}ms
          </span>
        )}
      </div>

      {/* Arguments (collapsed by default) */}
      {!collapsed && args && Object.keys(args).length > 0 && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">参数:</div>
          <pre className="text-xs bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-auto max-h-32">
            {JSON.stringify(args, null, 2)}
          </pre>
        </div>
      )}

      {/* Result */}
      {!collapsed && result !== undefined && status === 'success' && (
        <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">结果:</div>
          <pre className="text-xs bg-gray-100 dark:bg-gray-800 rounded p-2 overflow-auto max-h-32">
            {typeof result === 'string' ? result : JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-2 pt-2 border-t border-red-200 dark:border-red-600">
          <div className="text-xs text-red-500">
            <AlertCircle size={12} className="inline mr-1" />
            {error}
          </div>
        </div>
      )}
    </div>
  );
}

export const ToolCallCard = memo(ToolCallCardComponent);

export default ToolCallCard;