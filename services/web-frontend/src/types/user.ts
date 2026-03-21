/** 用户信息 */
export interface User {
  id: string;
  username: string;
  email: string;
  roles: Role[];
  permissions: string[];
  status: 'active' | 'inactive' | 'suspended';
  last_login_at?: string;
  created_at: string;
}

/** 角色 */
export type Role = 'admin' | 'operator' | 'viewer';

/** 权限字符串 */
export type Permission = string;

/** 租户信息 */
export interface Tenant {
  id: string;
  name: string;
  tier: 'free' | 'standard' | 'premium' | 'enterprise';
  features: string[];
}

/** Token 配对 */
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

/** 登录请求 */
export interface LoginRequest {
  username: string;
  password: string;
  tenant_id?: string;
}

/** 登录响应 */
export interface LoginResponse {
  user: User;
  tenant: Tenant;
  tokens: TokenPair;
}

/** 刷新 Token 请求 */
export interface RefreshTokenRequest {
  refresh_token: string;
}

/** 刷新 Token 响应 */
export interface RefreshTokenResponse {
  tokens: TokenPair;
}