import { Empty, Button } from 'antd';
import { FileQuestion } from 'lucide-react';

interface EmptyStateProps {
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({
  description = '暂无数据',
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <Empty
        image={<FileQuestion className="w-16 h-16 text-gray-300" />}
        description={description}
      >
        {action && (
          <Button type="primary" onClick={action.onClick}>
            {action.label}
          </Button>
        )}
      </Empty>
    </div>
  );
}

export default EmptyState;