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
  const {
    url,
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    reconnectAttempts = 5,
    reconnectDelay = 3000,
    heartbeatInterval = 30000,
  } = options;

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
    }, heartbeatInterval);
  }, [heartbeatInterval]);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!accessToken) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        type: 'auth',
        token: accessToken,
      }));

      setState({ isConnected: true, isReconnecting: false, error: null });
      reconnectCountRef.current = 0;
      startHeartbeat();
      onConnect?.();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return;
        onMessage(data);
      } catch (e) {
        console.warn('Failed to parse WebSocket message:', event.data);
      }
    };

    ws.onerror = (error) => {
      setState((s) => ({ ...s, error }));
      onError?.(error);
    };

    ws.onclose = (event) => {
      stopHeartbeat();
      setState((s) => ({ ...s, isConnected: false }));
      onDisconnect?.();

      if (event.code !== 1000 && reconnectCountRef.current < reconnectAttempts) {
        reconnectCountRef.current += 1;
        setState((s) => ({ ...s, isReconnecting: true }));
        const delay = reconnectDelay * Math.pow(1.5, reconnectCountRef.current - 1);
        reconnectTimerRef.current = setTimeout(connect, delay);
      }
    };
  }, [url, accessToken, onMessage, onConnect, onDisconnect, onError, reconnectAttempts, reconnectDelay, startHeartbeat, stopHeartbeat]);

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