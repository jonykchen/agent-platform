package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;

/**
 * 模型配置实体
 * 映射 model_config 表
 *
 * <p>存储平台支持的 LLM 模型信息，包括能力参数和成本配置。
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "model_config", indexes = {
    @Index(name = "idx_model_provider", columnList = "provider")
})
public class ModelConfig {

    @Id
    @Column(name = "id", nullable = false, length = 64)
    private String id;

    @Column(name = "name", nullable = false, length = 128)
    private String name;

    @Column(name = "provider", nullable = false, length = 64)
    private String provider;

    @Column(name = "type", nullable = false, length = 32)
    @Builder.Default
    private String type = "chat";

    @Column(name = "context_window", nullable = false)
    private Integer contextWindow;

    @Column(name = "max_output_tokens", nullable = false)
    private Integer maxOutputTokens;

    /**
     * 模型能力 JSON
     * 示例: ["function_call", "streaming", "multi_turn"]
     */
    @Column(name = "capabilities", columnDefinition = "JSONB")
    @JdbcTypeCode(SqlTypes.JSON)
    private String capabilities;

    @Column(name = "cost_per_1k_input", nullable = false, precision = 10, scale = 6)
    @Builder.Default
    private BigDecimal costPer1kInput = BigDecimal.ZERO;

    @Column(name = "cost_per_1k_output", nullable = false, precision = 10, scale = 6)
    @Builder.Default
    private BigDecimal costPer1kOutput = BigDecimal.ZERO;

    @Column(name = "description")
    private String description;

    @Column(name = "enabled", nullable = false)
    @Builder.Default
    private Boolean enabled = true;

    @Column(name = "display_order", nullable = false)
    @Builder.Default
    private Integer displayOrder = 100;

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
