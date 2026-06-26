package com.platform.gateway.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.dto.config.FeatureFlags;
import com.platform.gateway.dto.config.QuotaConfig;
import com.platform.gateway.dto.config.SettingsConfig;
import com.platform.gateway.dto.request.UpdateSettingsRequest;
import com.platform.gateway.dto.response.ModelResponse;
import com.platform.gateway.dto.response.QuotaUsageResponse;
import com.platform.gateway.dto.response.TenantConfigResponse;
import com.platform.gateway.dto.response.UsageResponse;
import com.platform.gateway.entity.ModelConfig;
import com.platform.gateway.entity.Tenant;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.ModelConfigRepository;
import com.platform.gateway.repository.TenantQuotaRepository;
import com.platform.gateway.repository.TenantRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 租户服务
 *
 * <p>提供租户配置、配额、用量统计等功能。
 *
 * <p>【缓存策略】
 * <ul>
 *   <li>tenant-config: 租户配置缓存 10 分钟（变更频率低）</li>
 *   <li>tenant-usage: 用量统计缓存 5 分钟（需要一定实时性）</li>
 *   <li>model-configs: 模型配置缓存 30 分钟（极少变更）</li>
 * </ul>
 *
 * <p>【数据来源】
 * <ul>
 *   <li>租户配置：tenant 表 + JSONB 字段解析</li>
 *   <li>配额使用：agent_run 表实时聚合</li>
 *   <li>并发计数：Redis 原子计数</li>
 *   <li>模型列表：model_config 表</li>
 * </ul>
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TenantService {

    private final TenantRepository tenantRepository;
    private final TenantQuotaRepository tenantQuotaRepository;
    private final ModelConfigRepository modelConfigRepository;
    private final TenantContextService tenantContextService;
    private final AuditService auditService;
    private final ObjectMapper objectMapper;
    private final StringRedisTemplate redisTemplate;

    private static final String CONCURRENT_RUNS_KEY = "tenant:%s:concurrent_runs";

    // ==================== 查询方法 ====================

    /**
     * 获取租户配置
     *
     * <p>注意：暂不使用 Redis 缓存，因为 GenericJackson2JsonRedisSerializer
     * 反序列化时会丢失类型信息（LinkedHashMap -> TenantConfigResponse）。
     * 后续可通过注册 @JsonTypeInfo 或使用 StringRedisSerializer + 手动序列化解决。
     */
    @Transactional(readOnly = true)
    public TenantConfigResponse getTenantConfig(String tenantId) {
        log.debug("Getting tenant config for: {}", tenantId);

        Tenant tenant = getActiveTenant(tenantId);
        return buildTenantConfigResponse(tenant);
    }

    /**
     * 获取配额使用情况（实时计算）
     *
     * <p>从 agent_run 表聚合实时数据，不使用缓存以保证配额检查的准确性。
     */
    public QuotaUsageResponse getQuotaUsage(String tenantId) {
        log.debug("Getting quota usage for tenant: {}", tenantId);

        Tenant tenant = getActiveTenant(tenantId);
        QuotaConfig quotaConfig = parseQuotaConfig(tenant.getQuotaConfig());
        SettingsConfig settingsConfig = parseSettingsConfig(tenant.getSettingsConfig());

        // 今日 Token 使用量（从 agent_run 聚合）
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        Long dailyTokensUsed = tenantQuotaRepository.getDailyTokenUsage(tenantId, today);

        // 本月成本
        LocalDate monthStart = today.withDayOfMonth(1);
        Double monthlyCostUsed = tenantQuotaRepository.getMonthlyCostUsage(tenantId, monthStart, today);

        // 当前并发数（Redis 原子计数）
        Integer concurrentRunsCurrent = getConcurrentRunsCount(tenantId);

        return QuotaUsageResponse.builder()
                .dailyTokensUsed(dailyTokensUsed != null ? dailyTokensUsed : 0L)
                .dailyTokensLimit(quotaConfig.getDailyTokens())
                .monthlyCostUsed(monthlyCostUsed != null ? monthlyCostUsed : 0.0)
                .monthlyCostLimit(quotaConfig.getMonthlyCostUsd())
                .concurrentRunsCurrent(concurrentRunsCurrent)
                .concurrentRunsLimit(settingsConfig.getMaxConcurrentRuns())
                .build();
    }

    /**
     * 获取租户用量统计
     */
    @Cacheable(
        value = "tenant-usage",
        key = "#tenantId + ':' + T(java.time.LocalDate).now(T(java.time.ZoneOffset).UTC)",
        unless = "#result == null"
    )
    @Transactional(readOnly = true)
    public UsageResponse getUsage(String tenantId) {
        log.debug("Getting usage stats for tenant: {}", tenantId);

        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        LocalDate monthStart = today.withDayOfMonth(1);
        Instant now = Instant.now();

        // Token 统计
        TenantQuotaRepository.TokenUsageStats tokenStats =
                tenantQuotaRepository.getTokenStats(tenantId, monthStart, today);

        // 请求统计
        TenantQuotaRepository.RequestUsageStats requestStats =
                tenantQuotaRepository.getRequestStats(tenantId, monthStart, today);

        // 模型统计
        List<TenantQuotaRepository.ModelUsageStats> modelStatsList =
                tenantQuotaRepository.getModelStats(tenantId, monthStart, today);

        // 取 Top 模型
        UsageResponse.ModelStats topModel = modelStatsList.isEmpty() ? null :
                UsageResponse.ModelStats.builder()
                        .model(modelStatsList.get(0).getModel())
                        .calls(modelStatsList.get(0).getTotalCalls())
                        .tokens(modelStatsList.get(0).getTotalTokens())
                        .avgLatencyMs(modelStatsList.get(0).getAvgLatencyMs())
                        .build();

        return UsageResponse.builder()
                .tenantId(tenantId)
                .periodStart(monthStart.atStartOfDay(ZoneOffset.UTC).toInstant())
                .periodEnd(now)
                .tokenStats(UsageResponse.TokenStats.builder()
                        .totalTokens(tokenStats.getTotalTokens())
                        .inputTokens(0L)   // 暂无独立统计，由 totalTokens 覆盖
                        .outputTokens(0L)
                        .dailyAverage(tokenStats.getDailyAverage())
                        .build())
                .requestStats(UsageResponse.RequestStats.builder()
                        .totalRequests(requestStats.getTotalRequests())
                        .successfulRequests(requestStats.getSuccessfulRequests())
                        .failedRequests(requestStats.getFailedRequests())
                        .successRate(requestStats.getSuccessRate())
                        .avgResponseTimeMs(requestStats.getAvgResponseTimeMs())
                        .build())
                .modelStats(topModel)
                .build();
    }

    /**
     * 获取可用模型列表（带缓存）
     */
    @Cacheable(
        value = "model-configs",
        unless = "#result == null || #result.isEmpty()"
    )
    @Transactional(readOnly = true)
    public List<ModelResponse> getAvailableModels() {
        log.debug("Getting available models");

        return modelConfigRepository.findByEnabledTrueOrderByDisplayOrderAsc().stream()
                .map(this::toModelResponse)
                .toList();
    }

    // ==================== 写入方法 ====================

    /**
     * 更新租户设置
     *
     * <p>部分更新（PATCH 语义），仅更新请求中提供的字段。
     * 写操作立即失效缓存。
     */
    @Transactional
    @CacheEvict(value = "tenant-config", key = "#tenantId")
    public void updateSettings(String tenantId, UpdateSettingsRequest request) {
        log.info("Updating settings for tenant: {}", tenantId);

        Tenant tenant = getActiveTenant(tenantId);

        // 记录变更前状态（审计用）
        String beforeQuotaConfig = tenant.getQuotaConfig();
        String beforeFeatureFlags = tenant.getFeatureFlags();
        String beforeSettingsConfig = tenant.getSettingsConfig();

        // 解析并合并 quotaConfig
        Map<String, Object> quotaMap = parseJsonToMap(tenant.getQuotaConfig());
        if (request.getDailyTokens() != null) {
            quotaMap.put("daily_tokens", request.getDailyTokens());
        }
        if (request.getMaxSessions() != null) {
            quotaMap.put("max_sessions", request.getMaxSessions());
        }
        if (request.getMaxUsers() != null) {
            quotaMap.put("max_users", request.getMaxUsers());
        }
        if (request.getMaxApiKeys() != null) {
            quotaMap.put("max_api_keys", request.getMaxApiKeys());
        }

        // 解析并合并 featureFlags
        Map<String, Object> featureMap = parseJsonToMap(tenant.getFeatureFlags());
        if (request.getFeatureFlags() != null) {
            featureMap.putAll(request.getFeatureFlags());
        }

        // 解析并合并 settingsConfig
        Map<String, Object> settingsMap = parseJsonToMap(tenant.getSettingsConfig());
        if (request.getDefaultModel() != null) {
            settingsMap.put("default_model", request.getDefaultModel());
        }
        if (request.getFallbackModel() != null) {
            settingsMap.put("fallback_model", request.getFallbackModel());
        }

        // 更新实体
        tenant.setQuotaConfig(toJson(quotaMap));
        tenant.setFeatureFlags(toJson(featureMap));
        tenant.setSettingsConfig(toJson(settingsMap));

        tenantRepository.save(tenant);

        // 记录审计日志
        auditService.recordEvent(
            AuditService.builder(tenantId, tenantContextService.getCurrentUserId())
                .type("tenant.config_changed", "tenant")
                .severity("info")
                .action("update_settings")
                .resource("tenant", tenantId)
                .beforeState(Map.of(
                    "quotaConfig", beforeQuotaConfig,
                    "featureFlags", beforeFeatureFlags,
                    "settingsConfig", beforeSettingsConfig
                ))
                .afterState(Map.of(
                    "quotaConfig", tenant.getQuotaConfig(),
                    "featureFlags", tenant.getFeatureFlags(),
                    "settingsConfig", tenant.getSettingsConfig()
                ))
                .build()
        );

        log.info("Settings updated successfully for tenant: {}", tenantId);
    }

    /**
     * 重置租户设置为默认配置
     *
     * <p>根据租户 tier 获取默认配置，覆盖现有配置。
     */
    @Transactional
    @CacheEvict(value = {"tenant-config", "tenant-usage"}, key = "#tenantId")
    public void resetSettings(String tenantId) {
        log.info("Resetting settings for tenant: {}", tenantId);

        Tenant tenant = getActiveTenant(tenantId);
        String tier = tenant.getTier();

        // 根据 tier 获取默认配置
        QuotaConfig defaultQuota = QuotaConfig.defaultForTier(tier);
        FeatureFlags defaultFeatures = FeatureFlags.defaultForTier(tier);
        SettingsConfig defaultSettings = SettingsConfig.defaultForTier(tier);

        // 更新实体
        tenant.setQuotaConfig(toJson(defaultQuota));
        tenant.setFeatureFlags(toJson(defaultFeatures));
        tenant.setSettingsConfig(toJson(defaultSettings));

        tenantRepository.save(tenant);

        // 记录审计日志
        auditService.recordEvent(
            AuditService.builder(tenantId, tenantContextService.getCurrentUserId())
                .type("tenant.config_reset", "tenant")
                .severity("warning")
                .action("reset_settings")
                .resource("tenant", tenantId)
                .details(Map.of("tier", tier))
                .build()
        );

        log.info("Settings reset successfully for tenant: {}", tenantId);
    }

    // ==================== 辅助方法 ====================

    /**
     * 获取活跃租户
     */
    private Tenant getActiveTenant(String tenantId) {
        return tenantRepository.findByIdAndStatus(tenantId, "active")
                .orElseThrow(() -> BusinessException.of(
                        ErrorCode.ERR_TENANT_NOT_FOUND,
                        "Tenant not found: " + tenantId
                ));
    }

    /**
     * 构建租户配置响应（JSONB → DTO）
     */
    private TenantConfigResponse buildTenantConfigResponse(Tenant tenant) {
        QuotaConfig quotaConfig = parseQuotaConfig(tenant.getQuotaConfig());
        FeatureFlags featureFlags = parseFeatureFlags(tenant.getFeatureFlags());
        SettingsConfig settingsConfig = parseSettingsConfig(tenant.getSettingsConfig());

        // 构建设置
        TenantConfigResponse.TenantSettings settings = TenantConfigResponse.TenantSettings.builder()
                .maxSessionsPerUser(quotaConfig.getMaxSessions())
                .maxTokensPerDay(quotaConfig.getDailyTokens())
                .maxConcurrentRuns(settingsConfig.getMaxConcurrentRuns())
                .allowedModels(settingsConfig.getAllowedModels())
                .defaultModel(settingsConfig.getDefaultModel())
                .enableKnowledgeBase(featureFlags.getRagEnabled())
                .enableMultiAgent(featureFlags.getMultiAgentEnabled())
                .dataRetentionDays(settingsConfig.getDataRetentionDays())
                .enableAuditLog(featureFlags.getAuditEnabled())
                .build();

        // 构建配额
        TenantConfigResponse.TenantQuotas quotas = TenantConfigResponse.TenantQuotas.builder()
                .dailyTokens(quotaConfig.getDailyTokens())
                .monthlyCostUsd(quotaConfig.getMonthlyCostUsd())
                .build();

        // 构建特性列表
        List<String> features = buildFeaturesList(featureFlags, tenant.getTier());

        return TenantConfigResponse.builder()
                .id(tenant.getId())
                .name(tenant.getName())
                .tier(tenant.getTier())
                .features(features)
                .settings(settings)
                .quotas(quotas)
                .createdAt(tenant.getCreatedAt())
                .updatedAt(tenant.getUpdatedAt())
                .build();
    }

    /**
     * 构建特性列表
     */
    private List<String> buildFeaturesList(FeatureFlags featureFlags, String tier) {
        List<String> features = new ArrayList<>();
        if (featureFlags.getRagEnabled()) {
            features.add("knowledge_base");
        }
        if (featureFlags.getMultiAgentEnabled()) {
            features.add("multi_agent");
        }
        if (featureFlags.getAuditEnabled()) {
            features.add("audit_log");
        }
        if (featureFlags.getApprovalWorkflow()) {
            features.add("approval_workflow");
        }
        return features;
    }

    /**
     * 解析 quotaConfig JSONB
     */
    private QuotaConfig parseQuotaConfig(String json) {
        try {
            if (json == null || json.isBlank()) {
                return QuotaConfig.defaultConfig();
            }
            return objectMapper.readValue(json, QuotaConfig.class);
        } catch (JsonProcessingException e) {
            log.warn("Failed to parse quotaConfig: {}", e.getMessage());
            return QuotaConfig.defaultConfig();
        }
    }

    /**
     * 解析 featureFlags JSONB
     */
    private FeatureFlags parseFeatureFlags(String json) {
        try {
            if (json == null || json.isBlank()) {
                return FeatureFlags.defaultFlags();
            }
            return objectMapper.readValue(json, FeatureFlags.class);
        } catch (JsonProcessingException e) {
            log.warn("Failed to parse featureFlags: {}", e.getMessage());
            return FeatureFlags.defaultFlags();
        }
    }

    /**
     * 解析 settingsConfig JSONB
     */
    private SettingsConfig parseSettingsConfig(String json) {
        try {
            if (json == null || json.isBlank()) {
                return SettingsConfig.defaultConfig();
            }
            return objectMapper.readValue(json, SettingsConfig.class);
        } catch (JsonProcessingException e) {
            log.warn("Failed to parse settingsConfig: {}", e.getMessage());
            return SettingsConfig.defaultConfig();
        }
    }

    /**
     * JSON 字符串 → Map
     */
    private Map<String, Object> parseJsonToMap(String json) {
        try {
            if (json == null || json.isBlank()) {
                return new HashMap<>();
            }
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (JsonProcessingException e) {
            log.warn("Failed to parse JSON to Map: {}", e.getMessage());
            return new HashMap<>();
        }
    }

    /**
     * 对象 → JSON 字符串
     */
    private String toJson(Object obj) {
        try {
            return objectMapper.writeValueAsString(obj);
        } catch (JsonProcessingException e) {
            log.error("Failed to serialize object to JSON: {}", e.getMessage());
            return "{}";
        }
    }

    /**
     * 获取当前并发运行数（Redis 原子计数）
     */
    private Integer getConcurrentRunsCount(String tenantId) {
        try {
            String key = String.format(CONCURRENT_RUNS_KEY, tenantId);
            String count = redisTemplate.opsForValue().get(key);
            return count != null ? Integer.parseInt(count) : 0;
        } catch (Exception e) {
            log.warn("Failed to get concurrent runs count from Redis: {}", e.getMessage());
            return 0;
        }
    }

    /**
     * ModelConfig → ModelResponse
     */
    private ModelResponse toModelResponse(ModelConfig config) {
        List<String> capabilities = parseCapabilities(config.getCapabilities());

        return ModelResponse.builder()
                .id(config.getId())
                .name(config.getName())
                .provider(config.getProvider())
                .type(config.getType())
                .contextWindow(config.getContextWindow())
                .maxOutputTokens(config.getMaxOutputTokens())
                .capabilities(capabilities)
                .description(config.getDescription())
                .enabled(config.getEnabled())
                .order(config.getDisplayOrder())
                .build();
    }

    /**
     * 解析 capabilities JSONB
     */
    private List<String> parseCapabilities(String json) {
        try {
            if (json == null || json.isBlank()) {
                return List.of();
            }
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (JsonProcessingException e) {
            log.warn("Failed to parse capabilities: {}", e.getMessage());
            return List.of();
        }
    }
}
