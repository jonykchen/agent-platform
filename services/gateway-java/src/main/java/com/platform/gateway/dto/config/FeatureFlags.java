package com.platform.gateway.dto.config;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 功能开关 JSONB 映射类
 *
 * <p>映射 tenant.feature_flags JSONB 字段。
 *
 * <p>【JSONB 结构】
 * <pre>
 * {
 *   "rag_enabled": true,
 *   "multi_agent_enabled": true,
 *   "audit_enabled": true,
 *   "approval_workflow": true
 * }
 * </pre>
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class FeatureFlags {

    @JsonProperty("rag_enabled")
    private Boolean ragEnabled = true;

    @JsonProperty("multi_agent_enabled")
    private Boolean multiAgentEnabled = true;

    @JsonProperty("audit_enabled")
    private Boolean auditEnabled = true;

    @JsonProperty("approval_workflow")
    private Boolean approvalWorkflow = true;

    /**
     * 获取默认功能开关
     */
    public static FeatureFlags defaultFlags() {
        return new FeatureFlags();
    }

    /**
     * 根据 tier 获取默认功能开关
     */
    public static FeatureFlags defaultForTier(String tier) {
        return switch (tier) {
            case "free" -> new FeatureFlags(false, false, true, false);
            case "standard" -> new FeatureFlags(true, false, true, false);
            case "premium" -> new FeatureFlags(true, true, true, true);
            case "enterprise" -> new FeatureFlags(true, true, true, true);
            default -> defaultFlags();
        };
    }
}
