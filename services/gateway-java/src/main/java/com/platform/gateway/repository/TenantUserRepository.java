package com.platform.gateway.repository;

import com.platform.gateway.entity.TenantUser;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 租户用户 Repository
 */
@Repository
public interface TenantUserRepository extends JpaRepository<TenantUser, UUID> {

    /**
     * 按租户ID查找所有用户
     */
    List<TenantUser> findByTenantId(String tenantId);

    /**
     * 按租户ID分页查找用户
     */
    Page<TenantUser> findByTenantId(String tenantId, Pageable pageable);

    /**
     * 按租户ID和用户ID查找
     */
    Optional<TenantUser> findByTenantIdAndUserId(String tenantId, String userId);

    /**
     * 按租户ID和用户名查找
     */
    Optional<TenantUser> findByTenantIdAndUsername(String tenantId, String username);

    /**
     * 按租户ID和状态查找
     */
    Page<TenantUser> findByTenantIdAndStatus(String tenantId, String status, Pageable pageable);

    /**
     * 按租户ID和角色查找
     */
    Page<TenantUser> findByTenantIdAndRole(String tenantId, String role, Pageable pageable);

    /**
     * 检查用户ID是否已存在
     */
    boolean existsByUserId(String userId);

    /**
     * 检查租户内用户ID是否已存在
     */
    boolean existsByTenantIdAndUserId(String tenantId, String userId);

    /**
     * 检查租户内用户名是否已存在
     */
    boolean existsByTenantIdAndUsername(String tenantId, String username);

    /**
     * 复杂查询：按条件筛选用户
     */
    @Query("SELECT tu FROM TenantUser tu WHERE tu.tenantId = :tenantId " +
           "AND (:status IS NULL OR tu.status = :status) " +
           "AND (:role IS NULL OR tu.role = :role)")
    Page<TenantUser> findByConditions(
        @Param("tenantId") String tenantId,
        @Param("status") String status,
        @Param("role") String role,
        Pageable pageable
    );

    /**
     * 按用户名查找（用于登录）
     */
    @Query("SELECT tu FROM TenantUser tu WHERE tu.username = :username")
    Optional<TenantUser> findByUsername(@Param("username") String username);

    /**
     * 按租户和用户名查找（用于登录）
     */
    @Query("SELECT tu FROM TenantUser tu WHERE tu.tenantId = :tenantId AND tu.username = :username")
    Optional<TenantUser> findByTenantIdAndUsernameForLogin(
        @Param("tenantId") String tenantId,
        @Param("username") String username
    );

    /**
     * 统计租户用户数
     */
    long countByTenantId(String tenantId);

    /**
     * 统计租户活跃用户数
     */
    long countByTenantIdAndStatus(String tenantId, String status);

    /**
     * 按用户ID查询所有关联的租户用户记录
     */
    List<TenantUser> findByUserId(String userId);
}
