import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useTenant } from './useTenant';
import { useAuthStore } from '@/stores/authStore';

describe('useTenant', () => {
  beforeEach(() => {
    useAuthStore.setState({
      tenant: null,
      user: null,
    });
  });

  it('should return null tenant when not authenticated', () => {
    const { result } = renderHook(() => useTenant());

    expect(result.current.tenant).toBeNull();
    expect(result.current.tenantId).toBeUndefined();
    expect(result.current.tenantName).toBeUndefined();
  });

  it('should return tenant data when authenticated', () => {
    const mockTenant = {
      id: 'tenant-123',
      name: 'Test Tenant',
      tier: 'enterprise' as const,
      features: ['chat', 'knowledge', 'tools'],
    };

    useAuthStore.setState({
      tenant: mockTenant,
      user: { id: 'user-1', roles: ['admin'] },
    });

    const { result } = renderHook(() => useTenant());

    expect(result.current.tenant).toEqual(mockTenant);
    expect(result.current.tenantId).toBe('tenant-123');
    expect(result.current.tenantName).toBe('Test Tenant');
    expect(result.current.tenantTier).toBe('enterprise');
    expect(result.current.features).toEqual(['chat', 'knowledge', 'tools']);
  });

  it('should check if feature is enabled', () => {
    const mockTenant = {
      id: 'tenant-123',
      name: 'Test Tenant',
      tier: 'enterprise' as const,
      features: ['chat', 'knowledge'],
    };

    useAuthStore.setState({
      tenant: mockTenant,
      user: { id: 'user-1', roles: ['admin'] },
    });

    const { result } = renderHook(() => useTenant());

    expect(result.current.isFeatureEnabled('chat')).toBe(true);
    expect(result.current.isFeatureEnabled('knowledge')).toBe(true);
    expect(result.current.isFeatureEnabled('tools')).toBe(false);
  });

  it('should return false for isFeatureEnabled when tenant is null', () => {
    const { result } = renderHook(() => useTenant());

    expect(result.current.isFeatureEnabled('chat')).toBe(false);
  });

  it('should identify enterprise tier', () => {
    const mockTenant = {
      id: 'tenant-123',
      name: 'Test Tenant',
      tier: 'enterprise' as const,
      features: [],
    };

    useAuthStore.setState({
      tenant: mockTenant,
      user: { id: 'user-1', roles: ['admin'] },
    });

    const { result } = renderHook(() => useTenant());

    expect(result.current.isEnterprise).toBe(true);
  });

  it('should identify premium tier as enterprise', () => {
    const mockTenant = {
      id: 'tenant-123',
      name: 'Test Tenant',
      tier: 'premium' as const,
      features: [],
    };

    useAuthStore.setState({
      tenant: mockTenant,
      user: { id: 'user-1', roles: ['admin'] },
    });

    const { result } = renderHook(() => useTenant());

    expect(result.current.isEnterprise).toBe(true);
  });

  it('should identify non-enterprise tier', () => {
    const mockTenant = {
      id: 'tenant-123',
      name: 'Test Tenant',
      tier: 'basic' as const,
      features: [],
    };

    useAuthStore.setState({
      tenant: mockTenant,
      user: { id: 'user-1', roles: ['admin'] },
    });

    const { result } = renderHook(() => useTenant());

    expect(result.current.isEnterprise).toBe(false);
  });

  it('should check if user is tenant admin', () => {
    useAuthStore.setState({
      tenant: { id: 'tenant-123', name: 'Test', tier: 'basic', features: [] },
      user: { id: 'user-1', roles: ['admin'] },
    });

    const { result } = renderHook(() => useTenant());

    expect(result.current.isTenantAdmin).toBe(true);
  });

  it('should return false for non-admin user', () => {
    useAuthStore.setState({
      tenant: { id: 'tenant-123', name: 'Test', tier: 'basic', features: [] },
      user: { id: 'user-1', roles: ['viewer'] },
    });

    const { result } = renderHook(() => useTenant());

    expect(result.current.isTenantAdmin).toBe(false);
  });

  it('should return false for isTenantAdmin when user is null', () => {
    const { result } = renderHook(() => useTenant());

    expect(result.current.isTenantAdmin).toBe(false);
  });
});
