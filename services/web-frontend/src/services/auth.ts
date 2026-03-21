import api from './api';
import type { LoginRequest, LoginResponse, RefreshTokenRequest, RefreshTokenResponse } from '@/types/user';

/**
 * 用户登录
 */
export async function login(request: LoginRequest): Promise<LoginResponse> {
  const response = await api.post<LoginResponse>('/auth/login', request);
  return response.data;
}

/**
 * 刷新 Token
 */
export async function refreshToken(request: RefreshTokenRequest): Promise<RefreshTokenResponse> {
  const response = await api.post<RefreshTokenResponse>('/auth/refresh', request);
  return response.data;
}

/**
 * 用户登出
 */
export async function logout(): Promise<void> {
  await api.post('/auth/logout');
}