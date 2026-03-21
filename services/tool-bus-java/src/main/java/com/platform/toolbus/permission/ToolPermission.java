package com.platform.toolbus.permission;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * 工具权限映射实体
 * 定义角色与工具的权限关系
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "tool_permission", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"tool_name", "role_name"})
})
public class ToolPermission {

    @Id
    @GeneratedValue
    private UUID id;

    @Column(name = "tool_name", nullable = false, length = 128)
    private String toolName;

    @Column(name = "role_name", nullable = false, length = 64)
    private String roleName;

    @Column(name = "allowed_actions", nullable = false, length = 32)
    @Builder.Default
    private String allowedActions = "execute";  // execute / read_only / approve

    @JdbcTypeCode(SqlTypes.JSONB)
    @Column(columnDefinition = "jsonb")
    @Builder.Default
    private Map<String, Object> conditions = Map.of();

    @JdbcTypeCode(SqlTypes.JSONB)
    @Column(name = "conditions_schema", columnDefinition = "jsonb")
    private Map<String, Object> conditionsSchema;

    @Column(name = "created_at", nullable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at", nullable = false)
    @Builder.Default
    private Instant updatedAt = Instant.now();
}
