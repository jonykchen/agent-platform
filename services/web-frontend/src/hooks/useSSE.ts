import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuthStore } from '@/stores/authStore';

export interface SSEOptions<T> {
  url: string;
  body?: Record<string, unknown>;
  onMessage: (data: T) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
  enabled?: boolean;
  retryAttempts?: number;
  retryDelay?: number;
}

export interface SSEState {
  isConnected: boolean;
  isStreaming: boolean;
  error: Error | null;
  retryCount: number;
}

interface SSEMessage {
  event?: string;
  id?: string;
  data: string;
}

function parseSSEMessages(
  chunk: string,
  buffer: string
): { messages: SSEMessage[]; remaining: string } {
  const messages: SSEMessage[] = [];
  const fullText = buffer + chunk;
  const lines = fullText.split('\n');
  const current: Partial<SSEMessage> = {};
  const remainingLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line === '') {
      if (current.data !== undefined) {
        messages.push(current as SSEMessage);
      }
      current = {};
    } else if (line.startsWith('event:')) {
      current.event = line.slice(6).trim();
    } else if (line.startsWith('id:')) {
      current.id = line.slice(3).trim();
    } else if (line.startsWith('data:')) {
      current.data = (current.data || '') + line.slice(5);
    } else if (i === lines.length - 1 && !line.endsWith('\n')) {
      remainingLines.push(line);
    }
  }

  return { messages, remaining: remainingLines.join('\n') };
}

export function useSSE<T = unknown>(options: SSEOptions<T>): SSEState & { connect: () => void; disconnect: () => void; retry: () => void } {
  const {
    url,
    body,
    onMessage,
    onError,
    onComplete,
    enabled = true,
    retryAttempts = 3,
    retryDelay = 1000,
  } = options;

  const abortControllerRef = useRef<AbortController | null>(null);
  const bufferRef = useRef<string>('');
  const lastEventIdRef = useRef<string>('');
  const retryCountRef = useRef(0);

  const [state, setState] = useState<SSEState>({
    isConnected: false,
    isStreaming: false,
    error: null,
    retryCount: 0,
  });

  const connect = useCallback(() => {
    if (!enabled) return;

    const { accessToken, tenant, user } = useAuthStore.getState();

    abortControllerRef.current = new AbortController();
    bufferRef.current = '';

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    };

    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }
    if (tenant) {
      headers['X-Tenant-ID'] = tenant.id;
    }
    if (user) {
      headers['X-User-ID'] = user.id;
    }
    if (lastEventIdRef.current) {
      headers['Last-Event-ID'] = lastEventIdRef.current;
    }

    fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
      signal: abortControllerRef.current.signal,
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        setState((s) => ({ ...s, isConnected: true, isStreaming: true, error: null }));

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        const readChunk = (): Promise<void> | undefined => {
          return reader?.read().then(({ done, value }) => {
            if (done) {
              setState((s) => ({ ...s, isStreaming: false }));
              onComplete?.();
              return;
            }

            const chunk = decoder.decode(value, { stream: true });
            const { messages, remaining } = parseSSEMessages(chunk, bufferRef.current);
            bufferRef.current = remaining;

            for (const msg of messages) {
              if (msg.id) {
                lastEventIdRef.current = msg.id;
              }
              if (msg.event === 'heartbeat') {
                continue;
              }
              try {
                const data = JSON.parse(msg.data) as T;
                onMessage(data);
              } catch (e) {
                console.warn('Failed to parse SSE message:', msg.data);
              }
            }

            return readChunk();
          });
        };

        return readChunk();
      })
      .catch((error) => {
        if (error.name === 'AbortError') {
          setState((s) => ({ ...s, isStreaming: false }));
          return;
        }

        setState((s) => ({ ...s, error, isStreaming: false }));
        onError?.(error);

        if (retryCountRef.current < retryAttempts) {
          retryCountRef.current += 1;
          setState((s) => ({ ...s, retryCount: retryCountRef.current }));
          const delay = retryDelay * Math.pow(2, retryCountRef.current - 1);
          setTimeout(connect, delay);
        }
      });
  }, [url, body, enabled, onMessage, onError, onComplete, retryAttempts, retryDelay]);

  const disconnect = useCallback(() => {
    abortControllerRef.current?.abort();
    setState((s) => ({ ...s, isConnected: false, isStreaming: false }));
  }, []);

  const retry = useCallback(() => {
    retryCountRef.current = 0;
    lastEventIdRef.current = '';
    setState((s) => ({ ...s, retryCount: 0, error: null }));
    connect();
  }, [connect]);

  useEffect(() => {
    if (enabled) {
      connect();
    }
    return disconnect;
  }, [enabled, connect, disconnect]);

  return {
    ...state,
    connect,
    disconnect,
    retry,
  };
}

export default useSSE;