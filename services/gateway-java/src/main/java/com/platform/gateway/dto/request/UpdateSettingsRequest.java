package com.platform.gateway.dto.request;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Map;

/**
 * 更新租户设置请求 DTO
 *
 * <p>用于更新租户的配置信息，支持部分更新（PATCH 语义）。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>PATCH /api/v1/tenants/{tenantId}/settings - 更新租户设置</li>
 * </ul>
 *
 * <p>【权限要求】tenant:write
 *
 * @see com.platform.gateway.controller.TenantController#updateSettings
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UpdateSettingsRequest {

    /**
     * 每日 Token 配额
     *
     * <p>限制租户每日可使用的 Token 数量。
     *
     * <p>【范围】10000 ~ 1000000000
     */
    @JsonProperty("daily_tokens")
    @Min(value = 10000, message = "每日 Token 配额不能小于 10000")
    @Max(value = 1000000000L, message = "每日 Token 配额不能超过 1000000000")
    private Long dailyTokens;

    /**
     * 最大并发会话数
     *
     * <p>限制租户同时活跃的会话数量。
     *
     * <p>【范围】1 ~ 10000
     */
    @JsonProperty("max_sessions")
    @Min(value = 1, message = "最大会话数不能小于 1")
    @Max(value = 10000, message = "最大会话数不能超过 10000")
    private Integer maxSessions;

    /**
     * 最大用户数
     *
     * <p>限制租户可创建的用户数量。
     *
     * <p>【范围】1 ~ 10000
     */
    @JsonProperty("max_users")
    @Min(value = 1, message = "最大用户数不能小于 1")
    @Max(value = 10000, message = "最大用户数不能超过 10000")
    private Integer maxUsers;

    /**
     * 最大 API Key 数
     *
     * <p>限制租户可创建的 API Key 数量。
     *
     * <p>【范围】1 ~ 1000
     */
    @JsonProperty("max_api_keys")
    @Min(value = 1, message = "最大 API Key 数不能小于 1")
    @Max(value = 1000, message = "最大 API Key 数不能超过 1000")
    private Integer maxApiKeys;

    /**
     * 功能开关配置
     *
     * <p>用于开启或关闭特定功能模块。
     *
     * <p>【示例】
     * <pre>
     * {
     *   "rag_enabled": true,
     *   "multi_modal_enabled": false,
     *   "streaming_enabled": true
     * }
     * </pre>
     */
    @JsonProperty("feature_flags")
    private Map<String, Object> featureFlags;

    /**
     * 默认模型设置
     *
     * <p>设置租户默认使用的模型。
     */
    @JsonProperty("default_model")
    @Size(max = 64, message = "模型名称长度不能超过 64 个字符")
    private String defaultModel;

    /**
     * 备选模型设置
     *
     * <p>当默认模型不可用时使用的备选模型。
     */
    @JsonProperty("fallback_model")
    @Size(max = 64, message = "模型名称长度不能超过 64 个字符")
    private String fallbackModel;

    /**
     * 系统提示词模板
     *
     * <p>租户级别的系统提示词，会追加到所有对话中。
     *
     * <p>【长度限制】最大 4000 字符
     */
    @JsonProperty("system_prompt")
    @Size(max = 4000, message = "系统提示词长度不能超过 4000 个字符")
    private String systemPrompt;
}
