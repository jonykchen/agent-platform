import { useState, useCallback } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useAuthStore } from '@/stores/authStore';
import { login as loginApi, logout as logoutApi } from '@/services/auth';
import type { LoginRequest, User, Tenant, TokenPair } from '@/types/user';

interface UseAuthReturn {
  user: User | null;
  tenant: Tenant | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (request: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const navigate = useNavigate();
  const { user, tenant, isAuthenticated, login: setAuth, logout: clearAuth } = useAuthStore();
  const [isLoading, setIsLoading] = useState(false);

  const login = useCallback(async (request: LoginRequest) => {
    setIsLoading(true);
    try {
      const response = await loginApi(request);
      setAuth(response.tokens, response.user, response.tenant);
    } finally {
      setIsLoading(false);
    }
  }, [setAuth]);

  const logout = useCallback(async () => {
    try {
      await logoutApi();
    } finally {
      clearAuth();
      navigate({ to: '/login' });
    }
  }, [clearAuth, navigate]);

  return {
    user,
    tenant,
    isAuthenticated,
    isLoading,
    login,
    logout,
  };
}