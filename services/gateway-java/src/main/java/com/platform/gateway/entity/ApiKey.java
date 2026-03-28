package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

/**
 * API Key 实体
 *
 * 用于服务间调用和外部系统集成的认证凭证
 *
 * 【API Key 格式】
 * - svc_* : 服务间调用（内部服务）
 * - ext_* : 外部系统集成
 * - test_* : 测试环境
 *
 * 【安全注意事项】
 * - key_hash 存储 SHA-256 哈希值，不存储明文
 * - key_prefix 存储前缀用于快速查找（如 "ext_abc..."）
 * - 生产环境必须设置过期时间
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "api_keys", indexes = {
    @Index(name = "idx_api_keys_prefix", columnList = "key_prefix"),
    @Index(name = "idx_api_keys_tenant", columnList = "tenant_id"),
    @Index(name = "idx_api_keys_active", columnList = "is_active")
})
public class ApiKey {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * API Key 的 SHA-256 哈希值
     * 用于安全验证，不存储明文
     */
    @Column(name = "key_hash", nullable = false, unique = true, length = 64)
    private String keyHash;

    /**
     * API Key 前缀（前8个字符）
     * 用于快速定位和查找
     */
    @Column(name = "key_prefix", nullable = false, length = 8)
    private String keyPrefix;

    /**
     * 所属租户 ID
     */
    @Column(name = "tenant_id", nullable = false, length = 32)
    private String tenantId;

    /**
     * 关联用户 ID（可选）
     */
    @Column(name = "user_id", length = 32)
    private String userId;

    /**
     * API Key 名称（便于管理）
     */
    @Column(name = "name", nullable = false, length = 100)
    private String name;

    /**
     * API Key 类型
     */
    @Enumerated(EnumType.STRING)
    @Column(name = "type", nullable = false, length = 16)
    private ApiKeyType type;

    /**
     * 权限范围
     */
    @ElementCollection
    @CollectionTable(
        name = "api_key_scopes",
        joinColumns = @JoinColumn(name = "api_key_id")
    )
    @Column(name = "scope")
    @Builder.Default
    private Set<String> scopes = new HashSet<>();

    /**
     * 每小时请求限制
     */
    @Column(name = "rate_limit")
    @Builder.Default
    private Integer rateLimit = 1000;

    /**
     * 过期时间（null 表示永不过期）
     */
    @Column(name = "expires_at")
    private Instant expiresAt;

    /**
     * 最后使用时间
     */
    @Column(name = "last_used_at")
    private Instant lastUsedAt;

    /**
     * 是否激活
     */
    @Column(name = "is_active", nullable = false)
    @Builder.Default
    private Boolean isActive = true;

    /**
     * 创建人
     */
    @Column(name = "created_by", length = 32)
    private String createdBy;

    /**
     * 创建时间
     */
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    /**
     * 更新时间
     */
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    public void prePersist() {
        Instant now = Instant.now();
        if (createdAt == null) {
            createdAt = now;
        }
        if (updatedAt == null) {
            updatedAt = now;
        }
        if (scopes == null) {
            scopes = new HashSet<>();
        }
        if (rateLimit == null) {
            rateLimit = 1000;
        }
        if (isActive == null) {
            isActive = true;
        }
    }

    @PreUpdate
    public void preUpdate() {
        updatedAt = Instant.now();
    }

    /**
     * 检查是否过期
     */
    public boolean isExpired() {
        return expiresAt != null && Instant.now().isAfter(expiresAt);
    }

    /**
     * 检查是否有效
     */
    public boolean isValid() {
        return isActive && !isExpired();
    }
}
