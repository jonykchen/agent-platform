import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

interface LoadingStateProps {
  tip?: string;
  size?: 'small' | 'default' | 'large';
  fullScreen?: boolean;
}

export function LoadingState({
  tip = '加载中...',
  size = 'default',
  fullScreen = false,
}: LoadingStateProps) {
  if (fullScreen) {
    return (
      <div className="fixed inset-0 flex items-center justify-center bg-white dark:bg-gray-900 z-50">
        <Spin
          indicator={<LoadingOutlined style={{ fontSize: 32 }} spin />}
          tip={tip}
          size={size}
        />
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center py-12">
      <Spin
        indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />}
        tip={tip}
        size={size}
      />
    </div>
  );
}

export default LoadingState;