package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * 角色-权限映射实体
 * 映射 role_permission 表（RBAC 动态权限）
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "role_permission", uniqueConstraints = {
    @UniqueConstraint(name = "uk_role_permission", columnNames = {"role", "permission"})
}, indexes = {
    @Index(name = "idx_role_permission_role", columnList = "role")
})
public class RolePermission {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", updatable = false, nullable = false)
    private Long id;

    @Column(name = "role", nullable = false, length = 32)
    private String role;

    @Column(name = "permission", nullable = false, length = 64)
    private String permission;

    @Column(name = "description", length = 256)
    private String description;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;
}
