import api from './api';
import type { User, Role } from '@/types/user';
import type { PageResponse, PageRequest } from '@/types/common';

/** 用户查询参数 */
export interface UserQueryParams extends PageRequest {
  username?: string;
  email?: string;
  status?: 'active' | 'inactive' | 'suspended';
  role?: Role;
}

/** 创建用户请求 */
export interface CreateUserRequest {
  username: string;
  email: string;
  password: string;
  roles: Role[];
}

/** 更新用户请求 */
export interface UpdateUserRequest {
  username?: string;
  email?: string;
  roles?: Role[];
  status?: 'active' | 'inactive' | 'suspended';
}

/** 用户详情（含更多信息） */
export interface UserDetail extends User {
  last_login_ip?: string;
  login_count: number;
  failed_login_count: number;
  updated_at: string;
}

/**
 * 获取用户列表
 */
export async function getUsers(params: UserQueryParams): Promise<PageResponse<UserDetail>> {
  const response = await api.get<PageResponse<UserDetail>>('/users', { params });
  return response.data;
}

/**
 * 获取单个用户详情
 */
export async function getUser(userId: string): Promise<UserDetail> {
  const response = await api.get<UserDetail>(`/users/${userId}`);
  return response.data;
}

/**
 * 创建用户
 */
export async function createUser(data: CreateUserRequest): Promise<UserDetail> {
  const response = await api.post<UserDetail>('/users', data);
  return response.data;
}

/**
 * 更新用户
 */
export async function updateUser(userId: string, data: UpdateUserRequest): Promise<UserDetail> {
  const response = await api.patch<UserDetail>(`/users/${userId}`, data);
  return response.data;
}

/**
 * 禁用用户
 */
export async function disableUser(userId: string): Promise<void> {
  await api.post(`/users/${userId}/disable`);
}

/**
 * 启用用户
 */
export async function enableUser(userId: string): Promise<void> {
  await api.post(`/users/${userId}/enable`);
}

/**
 * 重置用户密码
 */
export async function resetUserPassword(userId: string): Promise<{ temporary_password: string }> {
  const response = await api.post<{ temporary_password: string }>(`/users/${userId}/reset-password`);
  return response.data;
}

/**
 * 获取角色列表
 */
export async function getRoles(): Promise<Array<{ name: Role; description: string; permissions: string[] }>> {
  const response = await api.get('/roles');
  return response.data;
}

/**
 * 获取所有权限列表
 */
export async function getPermissions(): Promise<Array<{ name: string; description: string; category: string }>> {
  const response = await api.get('/permissions');
  return response.data;
}
