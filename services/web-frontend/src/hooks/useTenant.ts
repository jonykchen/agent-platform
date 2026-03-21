import { useAuthStore } from '@/stores/authStore';

/** 租户上下文 Hook */
export function useTenant() {
  const tenant = useAuthStore((state) => state.tenant);
  const user = useAuthStore((state) => state.user);

  return {
    tenant,
    tenantId: tenant?.id,
    tenantName: tenant?.name,
    tenantTier: tenant?.tier,
    features: tenant?.features || [],

    /** 检查功能是否启用 */
    isFeatureEnabled: (feature: string): boolean => {
      return tenant?.features.includes(feature) ?? false;
    },

    /** 是否是企业版或更高 */
    isEnterprise: tenant?.tier === 'enterprise' || tenant?.tier === 'premium',

    /** 用户是否是租户管理员 */
    isTenantAdmin: user?.roles.includes('admin') ?? false,
  };
}