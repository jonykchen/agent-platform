import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useThrottle } from './useThrottle';

describe('useThrottle', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should call callback immediately on first call', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottle(callback, 300));

    act(() => {
      result.current();
    });

    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('should throttle subsequent calls', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottle(callback, 300));

    // First call - should execute
    act(() => {
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Second call within throttle period - should not execute
    act(() => {
      vi.advanceTimersByTime(100);
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Third call within throttle period - should not execute
    act(() => {
      vi.advanceTimersByTime(100);
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('should allow call after throttle period', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottle(callback, 300));

    // First call
    act(() => {
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Wait for throttle period to expire
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Second call after throttle period - should execute
    act(() => {
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it('should use default delay of 300ms', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottle(callback));

    // First call
    act(() => {
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Call at 299ms - should not execute
    act(() => {
      vi.advanceTimersByTime(299);
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Call at 300ms - should execute
    act(() => {
      vi.advanceTimersByTime(1);
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it('should pass arguments to callback', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottle(callback, 300));

    act(() => {
      result.current('arg1', 'arg2');
    });

    expect(callback).toHaveBeenCalledWith('arg1', 'arg2');
  });

  it('should use latest callback', () => {
    const callback1 = vi.fn();
    const callback2 = vi.fn();

    const { result, rerender } = renderHook(
      ({ cb }) => useThrottle(cb, 300),
      { initialProps: { cb: callback1 } }
    );

    // First call with callback1
    act(() => {
      result.current();
    });
    expect(callback1).toHaveBeenCalledTimes(1);

    // Wait for throttle period
    act(() => {
      vi.advanceTimersByTime(300);
    });

    // Update callback
    rerender({ cb: callback2 });

    // Second call should use callback2
    act(() => {
      result.current();
    });
    expect(callback2).toHaveBeenCalledTimes(1);
    expect(callback1).toHaveBeenCalledTimes(1); // callback1 should not be called again
  });

  it('should work with custom delay', () => {
    const callback = vi.fn();
    const { result } = renderHook(() => useThrottle(callback, 500));

    // First call
    act(() => {
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Call at 400ms - should not execute
    act(() => {
      vi.advanceTimersByTime(400);
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Call at 500ms - should execute
    act(() => {
      vi.advanceTimersByTime(100);
      result.current();
    });
    expect(callback).toHaveBeenCalledTimes(2);
  });
});
