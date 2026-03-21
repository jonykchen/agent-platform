package com.platform.toolbus.permission;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 租户工具配置 Repository
 */
@Repository
public interface TenantToolConfigRepository extends JpaRepository<TenantToolConfig, TenantToolConfigId> {

    /**
     * 根据租户ID查找所有工具配置
     */
    List<TenantToolConfig> findByTenantId(String tenantId);

    /**
     * 根据租户ID和工具名查找配置
     */
    Optional<TenantToolConfig> findByTenantIdAndToolName(String tenantId, String toolName);

    /**
     * 查找所有启用的工具配置
     */
    List<TenantToolConfig> findByIsEnabledTrue();
}
