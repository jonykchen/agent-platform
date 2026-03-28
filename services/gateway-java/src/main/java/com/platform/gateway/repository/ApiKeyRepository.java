package com.platform.gateway.repository;

import com.platform.gateway.entity.ApiKey;
import com.platform.gateway.entity.ApiKeyType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * API Key Repository
 */
@Repository
public interface ApiKeyRepository extends JpaRepository<ApiKey, UUID> {

    /**
     * 按租户查找所有 API Key
     */
    List<ApiKey> findByTenantId(String tenantId);

    /**
     * 按租户查找活跃的 API Key
     */
    List<ApiKey> findByTenantIdAndIsActiveTrue(String tenantId);

    /**
     * 按哈希值查找（用于认证）
     */
    Optional<ApiKey> findByKeyHash(String keyHash);

    /**
     * 按前缀查找（用于快速定位）
     */
    Optional<ApiKey> findByKeyPrefixAndIsActiveTrue(String keyPrefix);

    /**
     * 按类型查找
     */
    List<ApiKey> findByType(ApiKeyType type);

    /**
     * 按租户和类型查找
     */
    List<ApiKey> findByTenantIdAndType(String tenantId, ApiKeyType type);

    /**
     * 检查哈希值是否已存在
     */
    boolean existsByKeyHash(String keyHash);

    /**
     * 更新最后使用时间
     */
    @Modifying
    @Query("UPDATE ApiKey ak SET ak.lastUsedAt = :lastUsedAt WHERE ak.id = :id")
    void updateLastUsedAt(@Param("id") UUID id, @Param("lastUsedAt") Instant lastUsedAt);

    /**
     * 查找已过期的 API Key
     */
    @Query("SELECT ak FROM ApiKey ak WHERE ak.expiresAt IS NOT NULL AND ak.expiresAt < :now")
    List<ApiKey> findExpiredKeys(@Param("now") Instant now);

    /**
     * 统计租户的活跃 API Key 数量
     */
    long countByTenantIdAndIsActiveTrue(String tenantId);

    /**
     * 按哈希值和活跃状态查找（用于认证）
     */
    @Query("SELECT ak FROM ApiKey ak WHERE ak.keyHash = :keyHash AND ak.isActive = true")
    Optional<ApiKey> findActiveByKeyHash(@Param("keyHash") String keyHash);

    /**
     * 按前缀和活跃状态查找（用于认证）
     */
    @Query("SELECT ak FROM ApiKey ak WHERE ak.keyPrefix = :keyPrefix AND ak.isActive = true " +
           "AND (ak.expiresAt IS NULL OR ak.expiresAt > :now)")
    Optional<ApiKey> findValidByKeyPrefix(
        @Param("keyPrefix") String keyPrefix,
        @Param("now") Instant now
    );
}