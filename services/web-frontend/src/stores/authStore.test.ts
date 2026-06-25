import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAuthStore, isTokenExpired, isTokenExpiringSoon } from './authStore';
import type { User, Tenant, TokenPair } from '@/types/user';

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

describe('authStore', () => {
  const mockUser: User = {
    id: 'user-123',
    email: 'test@example.com',
    name: 'Test User',
    roles: ['admin'],
  };

  const mockTenant: Tenant = {
    id: 'tenant-123',
    name: 'Test Tenant',
  };

  const mockTokens: TokenPair = {
    access_token: 'access-token-123',
    refresh_token: 'refresh-token-123',
    expires_in: 3600,
  };

  beforeEach(() => {
    // Reset store state before each test
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      expiresAt: null,
      user: null,
      tenant: null,
      isAuthenticated: false,
    });
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('should have correct initial state', () => {
      const state = useAuthStore.getState();

      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.expiresAt).toBeNull();
      expect(state.user).toBeNull();
      expect(state.tenant).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });
  });

  describe('login', () => {
    it('should set authentication state on login', () => {
      const { login } = useAuthStore.getState();

      login(mockTokens, mockUser, mockTenant);

      const state = useAuthStore.getState();
      expect(state.accessToken).toBe(mockTokens.access_token);
      expect(state.refreshToken).toBe(mockTokens.refresh_token);
      expect(state.user).toEqual(mockUser);
      expect(state.tenant).toEqual(mockTenant);
      expect(state.isAuthenticated).toBe(true);
      expect(state.expiresAt).toBeGreaterThan(Date.now());
    });

    it('should calculate correct expiration time', () => {
      const { login } = useAuthStore.getState();
      const now = Date.now();

      login(mockTokens, mockUser, mockTenant);

      const state = useAuthStore.getState();
      expect(state.expiresAt).toBeGreaterThanOrEqual(now + mockTokens.expires_in * 1000 - 1000);
      expect(state.expiresAt).toBeLessThanOrEqual(now + mockTokens.expires_in * 1000 + 1000);
    });
  });

  describe('logout', () => {
    it('should clear all authentication state on logout', () => {
      // First login
      const { login, logout } = useAuthStore.getState();
      login(mockTokens, mockUser, mockTenant);

      // Then logout
      logout();

      const state = useAuthStore.getState();
      expect(state.accessToken).toBeNull();
      expect(state.refreshToken).toBeNull();
      expect(state.expiresAt).toBeNull();
      expect(state.user).toBeNull();
      expect(state.tenant).toBeNull();
      expect(state.isAuthenticated).toBe(false);
    });

    it('should remove auth-storage from localStorage', () => {
      const { logout } = useAuthStore.getState();

      logout();

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('auth-storage');
    });
  });

  describe('refreshTokens', () => {
    it('should update tokens and expiration on refresh', () => {
      const { login, refreshTokens } = useAuthStore.getState();

      // First login
      login(mockTokens, mockUser, mockTenant);

      // Refresh with new tokens
      const newTokens: TokenPair = {
        access_token: 'new-access-token',
        refresh_token: 'new-refresh-token',
        expires_in: 7200,
      };

      refreshTokens(newTokens);

      const state = useAuthStore.getState();
      expect(state.accessToken).toBe(newTokens.access_token);
      expect(state.refreshToken).toBe(newTokens.refresh_token);
      // User and tenant should remain unchanged
      expect(state.user).toEqual(mockUser);
      expect(state.tenant).toEqual(mockTenant);
    });
  });

  describe('updateUser', () => {
    it('should update user data partially', () => {
      const { login, updateUser } = useAuthStore.getState();

      // First login
      login(mockTokens, mockUser, mockTenant);

      // Update user
      updateUser({ name: 'Updated Name' });

      const state = useAuthStore.getState();
      expect(state.user?.name).toBe('Updated Name');
      expect(state.user?.email).toBe(mockUser.email);
    });

    it('should not update user if user is null', () => {
      const { updateUser } = useAuthStore.getState();

      updateUser({ name: 'Updated Name' });

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
    });
  });
});

describe('isTokenExpired', () => {
  beforeEach(() => {
    useAuthStore.setState({ expiresAt: null });
  });

  it('should return true if expiresAt is null', () => {
    expect(isTokenExpired()).toBe(true);
  });

  it('should return true if token is expired', () => {
    useAuthStore.setState({ expiresAt: Date.now() - 1000 });
    expect(isTokenExpired()).toBe(true);
  });

  it('should return false if token is not expired', () => {
    useAuthStore.setState({ expiresAt: Date.now() + 3600 * 1000 });
    expect(isTokenExpired()).toBe(false);
  });
});

describe('isTokenExpiringSoon', () => {
  beforeEach(() => {
    useAuthStore.setState({ expiresAt: null });
  });

  it('should return true if expiresAt is null', () => {
    expect(isTokenExpiringSoon()).toBe(true);
  });

  it('should return true if token expires within 60 seconds', () => {
    useAuthStore.setState({ expiresAt: Date.now() + 30 * 1000 }); // 30 seconds
    expect(isTokenExpiringSoon()).toBe(true);
  });

  it('should return false if token expires after 60 seconds', () => {
    useAuthStore.setState({ expiresAt: Date.now() + 120 * 1000 }); // 120 seconds
    expect(isTokenExpiringSoon()).toBe(false);
  });
});
