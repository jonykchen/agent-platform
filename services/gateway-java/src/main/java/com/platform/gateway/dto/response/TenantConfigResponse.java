package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.List;

/**
 * 租户配置响应 DTO
 *
 * <p>匹配前端 TenantConfig 类型定义
 *
 * @see com.platform.gateway.controller.TenantController#getTenantConfig
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TenantConfigResponse {

    /**
     * 租户ID
     */
    private String id;

    /**
     * 租户名称
     */
    private String name;

    /**
     * 租户等级
     *
     * <p>可选值：free, standard, premium, enterprise
     */
    private String tier;

    /**
     * 功能特性列表
     */
    private List<String> features;

    /**
     * 租户设置
     */
    private TenantSettings settings;

    /**
     * 配额配置
     */
    private TenantQuotas quotas;

    /**
     * 创建时间
     */
    private Instant createdAt;

    /**
     * 更新时间
     */
    private Instant updatedAt;

    /**
     * 租户设置内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TenantSettings {

        private Integer maxSessionsPerUser;
        private Long maxTokensPerDay;
        private Integer maxConcurrentRuns;
        private List<String> allowedModels;
        private String defaultModel;
        private Boolean enableKnowledgeBase;
        private Boolean enableMultiAgent;
        private Integer dataRetentionDays;
        private Boolean enableAuditLog;
    }

    /**
     * 配额配置内部类
     */
    @Data
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class TenantQuotas {

        private Long dailyTokens;
        private Double monthlyCostUsd;
    }
}