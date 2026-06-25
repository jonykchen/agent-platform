import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useUIStore, initTheme } from './uiStore';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock matchMedia
window.matchMedia = vi.fn().mockImplementation((query) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}));

describe('uiStore', () => {
  beforeEach(() => {
    useUIStore.setState({
      theme: 'system',
      sidebarCollapsed: false,
      sidebarOpen: true,
    });
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should have correct initial state', () => {
      const state = useUIStore.getState();

      expect(state.theme).toBe('system');
      expect(state.sidebarCollapsed).toBe(false);
      expect(state.sidebarOpen).toBe(true);
    });
  });

  describe('setTheme', () => {
    it('should set theme to light', () => {
      const { setTheme } = useUIStore.getState();

      setTheme('light');

      expect(useUIStore.getState().theme).toBe('light');
    });

    it('should set theme to dark', () => {
      const { setTheme } = useUIStore.getState();

      setTheme('dark');

      expect(useUIStore.getState().theme).toBe('dark');
    });

    it('should set theme to system', () => {
      const { setTheme } = useUIStore.getState();

      setTheme('system');

      expect(useUIStore.getState().theme).toBe('system');
    });
  });

  describe('toggleSidebar', () => {
    it('should toggle sidebar state', () => {
      const { toggleSidebar } = useUIStore.getState();

      // Initial state: sidebarOpen = true, sidebarCollapsed = false
      toggleSidebar();

      const state = useUIStore.getState();
      expect(state.sidebarOpen).toBe(false);
      expect(state.sidebarCollapsed).toBe(true);

      // Toggle again
      toggleSidebar();

      const state2 = useUIStore.getState();
      expect(state2.sidebarOpen).toBe(true);
      expect(state2.sidebarCollapsed).toBe(false);
    });
  });

  describe('setSidebarCollapsed', () => {
    it('should set sidebar collapsed state', () => {
      const { setSidebarCollapsed } = useUIStore.getState();

      setSidebarCollapsed(true);

      expect(useUIStore.getState().sidebarCollapsed).toBe(true);

      setSidebarCollapsed(false);

      expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    });
  });

  describe('setSidebarOpen', () => {
    it('should set sidebar open state and sync collapsed', () => {
      const { setSidebarOpen } = useUIStore.getState();

      setSidebarOpen(false);

      const state = useUIStore.getState();
      expect(state.sidebarOpen).toBe(false);
      expect(state.sidebarCollapsed).toBe(true);

      setSidebarOpen(true);

      const state2 = useUIStore.getState();
      expect(state2.sidebarOpen).toBe(true);
      expect(state2.sidebarCollapsed).toBe(false);
    });
  });
});

describe('initTheme', () => {
  beforeEach(() => {
    document.documentElement.classList.remove('dark');
  });

  it('should apply light theme', () => {
    useUIStore.setState({ theme: 'light' });

    initTheme();

    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('should apply dark theme', () => {
    useUIStore.setState({ theme: 'dark' });

    initTheme();

    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('should apply system theme based on prefers-color-scheme', () => {
    useUIStore.setState({ theme: 'system' });

    // Mock system dark mode
    window.matchMedia = vi.fn().mockImplementation((query) => ({
      matches: query === '(prefers-color-scheme: dark)',
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    initTheme();

    expect(document.documentElement.classList.contains('dark')).toBe(true);
  });

  it('should apply system light theme when system prefers light', () => {
    useUIStore.setState({ theme: 'system' });

    // Mock system light mode
    window.matchMedia = vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));

    initTheme();

    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
