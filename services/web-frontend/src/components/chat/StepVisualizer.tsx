import { memo } from 'react';
import {
  Brain,
  Wrench,
  Eye,
  CheckCircle2,
  AlertCircle,
  Loader2,
  ShieldAlert,
  Clock,
  FileSearch,
} from 'lucide-react';
import clsx from 'clsx';
import type { AgentStepInfo, StepType } from '@/types/chat';

export interface StepVisualizerProps {
  steps: AgentStepInfo[];
  currentStepOrder?: number;
}

const STEP_ICONS: Record<StepType, React.ElementType> = {
  thinking: Brain,
  tool_call: Wrench,
  observation: Eye,
  final_answer: CheckCircle2,
  intent_classify: FileSearch,
  retrieve: FileSearch,
  risk_check: ShieldAlert,
  approval_wait: Clock,
};

const STEP_LABELS: Record<StepType, string> = {
  thinking: '思考中',
  tool_call: '工具调用',
  observation: '观察结果',
  final_answer: '生成回答',
  intent_classify: '意图识别',
  retrieve: '知识检索',
  risk_check: '风控检查',
  approval_wait: '等待审批',
};

function StepVisualizerComponent({ steps }: StepVisualizerProps) {
  if (steps.length === 0) return null;

  return (
    <div className="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4 mb-4">
      <div className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-3">
        执行步骤
      </div>
      <div className="space-y-2">
        {steps.map((step) => (
          <StepItem key={step.step_order} step={step} />
        ))}
      </div>
    </div>
  );
}

export const StepVisualizer = memo(StepVisualizerComponent);

interface StepItemProps {
  step: AgentStepInfo;
}

function StepItem({ step }: StepItemProps) {
  const Icon = STEP_ICONS[step.step_type] || Brain;
  const label = step.step_name || STEP_LABELS[step.step_type] || step.step_type;

  const statusStyles = {
    pending: 'text-gray-400 bg-gray-100 dark:bg-gray-700',
    running: 'text-blue-600 bg-blue-50 dark:bg-blue-900/30',
    completed: 'text-green-600 bg-green-50 dark:bg-green-900/30',
    failed: 'text-red-600 bg-red-50 dark:bg-red-900/30',
  };

  const iconStyles = {
    pending: 'text-gray-400',
    running: 'text-blue-600 animate-pulse',
    completed: 'text-green-600',
    failed: 'text-red-600',
  };

  return (
    <div
      className={clsx(
        'flex items-center gap-3 rounded-md px-3 py-2',
        statusStyles[step.status]
      )}
    >
      {/* 状态图标 */}
      <div className="flex-shrink-0">
        {step.status === 'running' ? (
          <Loader2 size={16} className={clsx('animate-spin', iconStyles[step.status])} />
        ) : step.status === 'failed' ? (
          <AlertCircle size={16} className={iconStyles[step.status]} />
        ) : step.status === 'completed' ? (
          <CheckCircle2 size={16} className={iconStyles[step.status]} />
        ) : (
          <Icon size={16} className={iconStyles[step.status]} />
        )}
      </div>

      {/* 步骤信息 */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{label}</span>
          {step.tool_name && (
            <span className="text-xs px-2 py-0.5 rounded bg-gray-200 dark:bg-gray-600">
              {step.tool_name}
            </span>
          )}
        </div>
        {step.thinking && step.status === 'running' && (
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">
            {step.thinking}
          </p>
        )}
      </div>

      {/* 步骤序号 */}
      <div className="text-xs text-gray-400">#{step.step_order}</div>
    </div>
  );
}

export default StepVisualizer;