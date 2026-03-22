package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;

/**
 * 租户实体
 * 映射 tenant 表
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "tenant")
public class Tenant {

    @Id
    @Column(name = "id", nullable = false, length = 64)
    private String id;

    @Column(name = "name", nullable = false, length = 256)
    private String name;

    @Column(name = "status", nullable = false, length = 32)
    @Builder.Default
    private String status = "active";

    /**
     * 配额配置 JSON
     * 示例: {"daily_tokens": 10000000, "max_sessions": 1000}
     */
    @Column(name = "quota_config", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private String quotaConfig;

    /**
     * 功能开关 JSON
     * 示例: {"rag_enabled": true, "multi_modal_enabled": false}
     */
    @Column(name = "feature_flags", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private String featureFlags;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    @PrePersist
    protected void onCreate() {
        Instant now = Instant.now();
        if (createdAt == null) {
            createdAt = now;
        }
        if (updatedAt == null) {
            updatedAt = now;
        }
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = Instant.now();
    }
}
