import { useRef, useCallback } from 'react';

export function useThrottle<T extends (...args: unknown[]) => void>(
  callback: T,
  delay: number = 300
): T {
  const lastCallRef = useRef(0);
  const callbackRef = useRef(callback);

  // 每次渲染更新 ref
  callbackRef.current = callback;

  return useCallback((...args: unknown[]) => {
    const now = Date.now();
    if (now - lastCallRef.current >= delay) {
      lastCallRef.current = now;
      // 使用 ref 调用最新回调
      callbackRef.current(...args);
    }
  }, [delay]) as T;
}

export default useThrottle;