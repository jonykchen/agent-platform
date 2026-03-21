import { useCallback, useRef } from 'react';

export function useThrottle<T extends (...args: unknown[]) => void>(
  callback: T,
  delay: number = 300
): T {
  const lastCallRef = useRef(0);

  return useCallback((...args: unknown[]) => {
    const now = Date.now();
    if (now - lastCallRef.current >= delay) {
      lastCallRef.current = now;
      callback(...args);
    }
  }, [callback, delay]) as T;
}

export default useThrottle;