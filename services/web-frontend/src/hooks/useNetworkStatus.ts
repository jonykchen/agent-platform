import { useState, useEffect } from 'react';
import { notification } from 'antd';

export interface NetworkStatus {
  isOnline: boolean;
  isSlowConnection: boolean;
  effectiveType: string;
  downlink: number;
}

export function useNetworkStatus(): NetworkStatus {
  const [status, setStatus] = useState<NetworkStatus>({
    isOnline: navigator.onLine,
    isSlowConnection: false,
    effectiveType: '4g',
    downlink: 10,
  });

  useEffect(() => {
    const handleOnline = () => {
      setStatus((s) => ({ ...s, isOnline: true }));
      notification.success({ message: '网络已恢复', duration: 2 });
    };

    const handleOffline = () => {
      setStatus((s) => ({ ...s, isOnline: false }));
      notification.warning({
        message: '网络已断开',
        description: '请检查网络连接',
        duration: 0,
      });
    };

    const connection = (navigator as Navigator & { connection?: ConnectionInfo }).connection;

    interface ConnectionInfo {
      effectiveType: string;
      downlink: number;
      addEventListener: (type: string, listener: () => void) => void;
      removeEventListener: (type: string, listener: () => void) => void;
    }

    // online/offline 事件始终监听，确保所有浏览器都能正确追踪网络状态
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    if (connection) {
      const handleConnectionChange = () => {
        setStatus((s) => ({
          ...s,
          isSlowConnection: connection.effectiveType === '2g' || connection.effectiveType === 'slow-2g',
          effectiveType: connection.effectiveType,
          downlink: connection.downlink,
        }));
      };
      connection.addEventListener('change', handleConnectionChange);
      handleConnectionChange();

      return () => {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
        connection.removeEventListener('change', handleConnectionChange);
      };
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return status;
}

export default useNetworkStatus;