import axios, { AxiosInstance, InternalAxiosRequestConfig, AxiosError } from 'axios';
import { useAuthStore } from '@/stores/authStore';
import { generateRequestId } from '@/utils/request';
import type { ErrorDetail } from '@/types/error';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：注入认证和多租户 Header
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const { accessToken, user, tenant } = useAuthStore.getState();

    // JWT Token
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }

    // 多租户 Header
    if (tenant) {
      config.headers['X-Tenant-ID'] = tenant.id;
    }

    if (user) {
      config.headers['X-User-ID'] = user.id;
    }

    // 请求追踪
    config.headers['X-Request-ID'] = generateRequestId();
    config.headers['X-Trace-ID'] = config.headers['X-Request-ID'];

    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器：处理错误和 Token 刷新
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Token 过期，尝试刷新
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // 正在刷新，等待刷新完成
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const { refreshToken } = useAuthStore.getState();
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        useAuthStore.getState().refreshTokens(data.tokens);
        const newToken = data.tokens.access_token;

        onTokenRefreshed(newToken);
        originalRequest.headers.Authorization = `Bearer ${newToken}`;

        return api(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().logout();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;

// 辅助函数：提取错误信息
export function extractErrorDetail(error: unknown): ErrorDetail | null {
  if (axios.isAxiosError(error)) {
    return error.response?.data?.error || null;
  }
  return null;
}