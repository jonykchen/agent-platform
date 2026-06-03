import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';

export interface WebSocketOptions<T> {
  url: string;
  onMessage: (data: T) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectDelay?: number;
  heartbeatInterval?: number;
}

export interface WebSocketState {
  isConnected: boolean;
  isReconnecting: boolean;
  error: Event | null;
}

export function useWebSocket<T = unknown>(options: WebSocketOptions<T>): WebSocketState & { send: (data: unknown) => void; disconnect: () => void; reconnect: () => void } {
  // 使用 ref 存储回调，避免依赖变化导致重新连接
  const onMessageRef = useRef(options.onMessage);
  const onConnectRef = useRef(options.onConnect);
  const onDisconnectRef = useRef(options.onDisconnect);
  const onErrorRef = useRef(options.onError);

  // 每次渲染更新 ref（ref 变化不触发重渲染）
  onMessageRef.current = options.onMessage;
  onConnectRef.current = options.onConnect;
  onDisconnectRef.current = options.onDisconnect;
  onErrorRef.current = options.onError;

  const { accessToken } = useAuthStore();
  const wsRef = useRef<WebSocket | null>(null);
  const heartbeatRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null);

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    isReconnecting: false,
    error: null,
  });

  const startHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
    }
    heartbeatRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, options.heartbeatInterval ?? 30000);
  }, [options.heartbeatInterval]);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  // connect 函数不依赖回调，只依赖稳定值
  const connect = useCallback(() => {
    if (!accessToken) return;

    const ws = new WebSocket(options.url);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'auth',
        token: accessToken,
      }));

      setState({ isConnected: true, isReconnecting: false, error: null });
      reconnectCountRef.current = 0;
      startHeartbeat();
      onConnectRef.current?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return;
        // 使用 ref 调用最新回调
        onMessageRef.current(data);
      } catch (e) {
        console.warn('Failed to parse WebSocket message:', event.data);
      }
    };

    ws.onerror = (error) => {
      setState((s) => ({ ...s, error }));
      onErrorRef.current?.(error);
    };

    ws.onclose = (event) => {
      stopHeartbeat();
      setState((s) => ({ ...s, isConnected: false }));
      onDisconnectRef.current?.();

      const reconnectAttempts = options.reconnectAttempts ?? 5;
      const reconnectDelay = options.reconnectDelay ?? 3000;

      if (event.code !== 1000 && reconnectCountRef.current < reconnectAttempts) {
        reconnectCountRef.current += 1;
        setState((s) => ({ ...s, isReconnecting: true }));
        const delay = reconnectDelay * Math.pow(1.5, reconnectCountRef.current - 1);
        reconnectTimerRef.current = setTimeout(connect, delay);
      }
    };
  }, [options.url, accessToken, options.reconnectAttempts, options.reconnectDelay, startHeartbeat, stopHeartbeat]);

  const disconnect = useCallback(() => {
    stopHeartbeat();
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000);
      wsRef.current = null;
    }
    setState({ isConnected: false, isReconnecting: false, error: null });
  }, [stopHeartbeat]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  const reconnect = useCallback(() => {
    reconnectCountRef.current = 0;
    connect();
  }, [connect]);

  useEffect(() => {
    connect();
    return disconnect;
  }, [connect, disconnect]);

  return {
    ...state,
    send,
    disconnect,
    reconnect,
  };
}

export default useWebSocket;