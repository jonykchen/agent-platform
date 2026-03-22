package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * 租户用户实体
 * 映射 tenant_user 表
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "tenant_user", uniqueConstraints = {
    @UniqueConstraint(name = "uk_tenant_user", columnNames = {"tenant_id", "user_id"}),
    @UniqueConstraint(name = "uk_tenant_username", columnNames = {"tenant_id", "username"})
}, indexes = {
    @Index(name = "idx_user_tenant_status", columnList = "tenant_id, status"),
    @Index(name = "idx_user_tenant_role", columnList = "tenant_id, role")
})
public class TenantUser {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Column(name = "user_id", nullable = false, length = 128)
    private String userId;

    @Column(name = "username", nullable = false, length = 64)
    private String username;

    @Column(name = "email", length = 256)
    private String email;

    @Column(name = "password", nullable = false, length = 256)
    private String password;

    @Column(name = "role", nullable = false, length = 32)
    private String role;

    @Column(name = "quota_daily", nullable = false)
    private Integer quotaDaily;

    @Column(name = "quota_used_today", nullable = false)
    private Integer quotaUsedToday;

    @Column(name = "status", nullable = false, length = 32)
    private String status;

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    @Column(name = "last_login_ip", length = 64)
    private String lastLoginIp;

    @Column(name = "login_count")
    @Builder.Default
    private Integer loginCount = 0;

    @Column(name = "failed_login_count")
    @Builder.Default
    private Integer failedLoginCount = 0;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

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
        if (quotaDaily == null) {
            quotaDaily = 100000;
        }
        if (quotaUsedToday == null) {
            quotaUsedToday = 0;
        }
        if (status == null) {
            status = "active";
        }
        if (role == null) {
            role = "viewer";
        }
        if (loginCount == null) {
            loginCount = 0;
        }
        if (failedLoginCount == null) {
            failedLoginCount = 0;
        }
    }

    @PreUpdate
    public void preUpdate() {
        updatedAt = Instant.now();
    }
}