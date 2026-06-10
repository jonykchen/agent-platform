package com.platform.gateway.service;

import com.platform.gateway.entity.RolePermission;
import com.platform.gateway.repository.RolePermissionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 角色权限解析服务（RBAC 动态权限）
 *
 * <p>从 {@code role_permission} 表加载角色→权限映射，替代历史硬编码 Map。
 * 带本地缓存（角色数量有限，缓存命中率高）与默认值兜底（DB 不可用时不致鉴权全失）。
 *
 * <p>权限粒度：{@code domain:action}（如 {@code user:write}、{@code approval:approve}）。
 * 角色 admin 拥有通配权限 {@code *}，鉴权时由 {@code @PreAuthorize("hasRole('admin') or ...")} 直接放行。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RolePermissionService {

    private final RolePermissionRepository rolePermissionRepository;

    /** 角色→权限缓存（懒加载，DB 变更后可调用 evict 失效） */
    private final Map<String, Set<String>> cache = new ConcurrentHashMap<>();

    /** DB 不可用时的默认映射（与 V006 种子数据一致） */
    private static final Map<String, String[]> DEFAULT_PERMISSIONS = Map.of(
        "admin", new String[]{"*"},
        "operator", new String[]{"chat:read", "chat:write", "approval:read", "approval:approve", "tools:execute"},
        "viewer", new String[]{"chat:read", "approval:read"},
        "member", new String[]{"chat:read", "chat:write", "approval:read"}
    );

    /**
     * 解析单个角色的权限集合。
     *
     * @param role 角色名
     * @return 权限集合（admin 含通配 {@code *}）
     */
    public Set<String> getPermissionsForRole(String role) {
        if (role == null || role.isBlank()) {
            return Set.of();
        }
        return cache.computeIfAbsent(role, this::loadFromDbOrDefault);
    }

    /**
     * 解析多个角色的合并权限集合。
     *
     * @param roles 角色数组
     * @return 合并后的权限集合
     */
    public Set<String> resolvePermissions(String[] roles) {
        if (roles == null || roles.length == 0) {
            return Set.of();
        }
        Set<String> all = new LinkedHashSet<>();
        for (String role : roles) {
            all.addAll(getPermissionsForRole(role));
        }
        return all;
    }

    private Set<String> loadFromDbOrDefault(String role) {
        try {
            List<RolePermission> rows = rolePermissionRepository.findByRole(role);
            if (!rows.isEmpty()) {
                Set<String> perms = new LinkedHashSet<>();
                for (RolePermission rp : rows) {
                    perms.add(rp.getPermission());
                }
                return perms;
            }
            log.warn("role_permission_empty_for_role role={}, falling back to defaults", role);
        } catch (Exception e) {
            log.error("role_permission_load_failed role={}, using defaults: {}", role, e.getMessage());
        }
        String[] defaults = DEFAULT_PERMISSIONS.get(role);
        return defaults != null ? new LinkedHashSet<>(Arrays.asList(defaults)) : Set.of();
    }

    /** 失效缓存（权限变更后调用，支持动态生效）。 */
    public void evictCache() {
        cache.clear();
        log.info("role_permission_cache_evicted");
    }
}
