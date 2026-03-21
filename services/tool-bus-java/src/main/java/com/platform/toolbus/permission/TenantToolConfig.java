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

/**
 * 租户级工具配置实体
 * 控制租户对工具的访问权限和配额
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "tenant_tool_config")
@IdClass(TenantToolConfigId.class)
public class TenantToolConfig {

    @Id
    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    @Id
    @Column(name = "tool_name", nullable = false, length = 128)
    private String toolName;

    @Column(name = "is_enabled", nullable = false)
    @Builder.Default
    private Boolean isEnabled = false;

    @Column(name = "daily_quota")
    private Integer dailyQuota;  // NULL = 无限制

    @Column(name = "monthly_quota")
    private Integer monthlyQuota;

    @JdbcTypeCode(SqlTypes.JSONB)
    @Column(columnDefinition = "jsonb")
    @Builder.Default
    private Map<String, Object> config = Map.of();

    @Column(name = "enabled_by", length = 128)
    private String enabledBy;

    @Column(name = "enabled_at")
    private Instant enabledAt;

    @Column(name = "disabled_reason", columnDefinition = "text")
    private String disabledReason;

    @Column(name = "created_at", nullable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();

    @Column(name = "updated_at", nullable = false)
    @Builder.Default
    private Instant updatedAt = Instant.now();
}
