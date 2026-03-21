import { useMemo } from 'react';
import { useAuthStore } from '@/stores/authStore';
import type { Role } from '@/types/user';

/** 权限定义 */
export const Permissions = {
  // 对话
  CHAT_READ: 'chat:read',
  CHAT_WRITE: 'chat:write',

  // 审批
  APPROVAL_READ: 'approval:read',
  APPROVAL_APPROVE: 'approval:approve',
  APPROVAL_REJECT: 'approval:reject',

  // 工具管理
  TOOL_READ: 'tool:read',
  TOOL_WRITE: 'tool:write',
  TOOL_DELETE: 'tool:delete',

  // 审计
  AUDIT_READ: 'audit:read',
  AUDIT_EXPORT: 'audit:export',

  // 租户
  TENANT_READ: 'tenant:read',
  TENANT_WRITE: 'tenant:write',

  // 用户
  USER_READ: 'user:read',
  USER_WRITE: 'user:write',

  // 监控
  DASHBOARD_READ: 'dashboard:read',
} as const;

/** 角色权限映射 */
export const RolePermissions: Record<Role, string[]> = {
  admin: Object.values(Permissions),
  operator: [
    Permissions.CHAT_READ,
    Permissions.CHAT_WRITE,
    Permissions.APPROVAL_READ,
    Permissions.APPROVAL_APPROVE,
    Permissions.APPROVAL_REJECT,
    Permissions.TOOL_READ,
    Permissions.AUDIT_READ,
    Permissions.DASHBOARD_READ,
    Permissions.USER_READ,
  ],
  viewer: [
    Permissions.CHAT_READ,
    Permissions.APPROVAL_READ,
    Permissions.TOOL_READ,
    Permissions.AUDIT_READ,
    Permissions.DASHBOARD_READ,
    Permissions.USER_READ,
  ],
};

/** 权限检查 Hook */
export function usePermission() {
  const user = useAuthStore((state) => state.user);

  const hasPermission = useMemo(() => {
    return (permission: string): boolean => {
      if (!user) return false;

      // 检查用户直接权限
      if (user.permissions.includes(permission) || user.permissions.includes('*')) {
        return true;
      }

      // 检查角色权限
      return user.roles.some((role) => RolePermissions[role]?.includes(permission));
    };
  }, [user]);

  const hasAnyPermission = useMemo(() => {
    return (permissions: string[]): boolean => {
      return permissions.some(hasPermission);
    };
  }, [hasPermission]);

  const hasAllPermissions = useMemo(() => {
    return (permissions: string[]): boolean => {
      return permissions.every(hasPermission);
    };
  }, [hasPermission]);

  const hasRole = useMemo(() => {
    return (role: Role): boolean => {
      return user?.roles.includes(role) ?? false;
    };
  }, [user]);

  const isAdmin = useMemo(() => {
    return user?.roles.includes('admin') ?? false;
  }, [user]);

  return {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    hasRole,
    isAdmin,
  };
}