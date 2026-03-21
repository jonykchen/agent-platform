import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User, Tenant, TokenPair, Role } from '@/types/user';

export interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  expiresAt: number | null;
  user: User | null;
  tenant: Tenant | null;
  isAuthenticated: boolean;

  login: (tokens: TokenPair, user: User, tenant: Tenant) => void;
  logout: () => void;
  refreshTokens: (tokens: TokenPair) => void;
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      expiresAt: null,
      user: null,
      tenant: null,
      isAuthenticated: false,

      login: (tokens, user, tenant) => {
        const expiresAt = Date.now() + tokens.expires_in * 1000;
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          expiresAt,
          user,
          tenant,
          isAuthenticated: true,
        });
      },

      logout: () => {
        set({
          accessToken: null,
          refreshToken: null,
          expiresAt: null,
          user: null,
          tenant: null,
          isAuthenticated: false,
        });
        localStorage.clear();
      },

      refreshTokens: (tokens) => {
        const expiresAt = Date.now() + tokens.expires_in * 1000;
        set({
          accessToken: tokens.access_token,
          refreshToken: tokens.refresh_token,
          expiresAt,
        });
      },

      updateUser: (userData) => {
        const { user } = get();
        if (user) {
          set({ user: { ...user, ...userData } });
        }
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        expiresAt: state.expiresAt,
        user: state.user,
        tenant: state.tenant,
      }),
    }
  )
);

// Token 过期检查
export function isTokenExpired(): boolean {
  const { expiresAt } = useAuthStore.getState();
  if (!expiresAt) return true;
  return Date.now() >= expiresAt;
}

// Token 即将过期检查（提前 60 秒）
export function isTokenExpiringSoon(): boolean {
  const { expiresAt } = useAuthStore.getState();
  if (!expiresAt) return true;
  return Date.now() >= expiresAt - 60 * 1000;
}