import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useNetworkStatus } from './useNetworkStatus';

// Mock antd notification
vi.mock('antd', () => ({
  notification: {
    success: vi.fn(),
    warning: vi.fn(),
  },
}));

describe('useNetworkStatus', () => {
  let onlineHandler: () => void;
  let offlineHandler: () => void;

  beforeEach(() => {
    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      value: true,
      writable: true,
    });

    // Mock window.addEventListener
    vi.spyOn(window, 'addEventListener').mockImplementation((event, handler) => {
      if (event === 'online') onlineHandler = handler as () => void;
      if (event === 'offline') offlineHandler = handler as () => void;
    });

    vi.spyOn(window, 'removeEventListener').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should return initial online status', () => {
    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(true);
  });

  it('should return initial offline status', () => {
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
    });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(false);
  });

  it('should update status when going online', () => {
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
    });

    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(false);

    // Simulate going online
    act(() => {
      onlineHandler();
    });

    expect(result.current.isOnline).toBe(true);
  });

  it('should update status when going offline', () => {
    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.isOnline).toBe(true);

    // Simulate going offline
    act(() => {
      offlineHandler();
    });

    expect(result.current.isOnline).toBe(false);
  });

  it('should call notification.success when going online', async () => {
    const { notification } = await import('antd');
    const { result } = renderHook(() => useNetworkStatus());

    act(() => {
      onlineHandler();
    });

    expect(notification.success).toHaveBeenCalledWith({
      message: '网络已恢复',
      duration: 2,
    });
  });

  it('should call notification.warning when going offline', async () => {
    const { notification } = await import('antd');
    const { result } = renderHook(() => useNetworkStatus());

    act(() => {
      offlineHandler();
    });

    expect(notification.warning).toHaveBeenCalledWith({
      message: '网络已断开',
      description: '请检查网络连接',
      duration: 0,
    });
  });

  it('should return default network info when connection API not available', () => {
    const { result } = renderHook(() => useNetworkStatus());

    expect(result.current.effectiveType).toBe('4g');
    expect(result.current.downlink).toBe(10);
    expect(result.current.isSlowConnection).toBe(false);
  });

  it('should register event listeners on mount', () => {
    renderHook(() => useNetworkStatus());

    expect(window.addEventListener).toHaveBeenCalledWith('online', expect.any(Function));
    expect(window.addEventListener).toHaveBeenCalledWith('offline', expect.any(Function));
  });

  it('should cleanup event listeners on unmount', () => {
    const { unmount } = renderHook(() => useNetworkStatus());

    unmount();

    expect(window.removeEventListener).toHaveBeenCalledWith('online', expect.any(Function));
    expect(window.removeEventListener).toHaveBeenCalledWith('offline', expect.any(Function));
  });
});
