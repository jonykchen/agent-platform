package com.platform.gateway.dto.config;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 运行配置 JSONB 映射类
 *
 * <p>映射 tenant.settings_config JSONB 字段。
 *
 * <p>【JSONB 结构】
 * <pre>
 * {
 *   "default_model": "qwen-plus",
 *   "allowed_models": ["qwen-max", "qwen-plus", "deepseek-chat", "glm-4"],
 *   "data_retention_days": 90,
 *   "max_concurrent_runs": 50
 * }
 * </pre>
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class SettingsConfig {

    @JsonProperty("default_model")
    private String defaultModel = "qwen-plus";

    @JsonProperty("allowed_models")
    private List<String> allowedModels = List.of("qwen-max", "qwen-plus", "deepseek-chat", "glm-4");

    @JsonProperty("data_retention_days")
    private Integer dataRetentionDays = 90;

    @JsonProperty("max_concurrent_runs")
    private Integer maxConcurrentRuns = 50;

    /**
     * 获取默认运行配置
     */
    public static SettingsConfig defaultConfig() {
        return new SettingsConfig();
    }

    /**
     * 根据 tier 获取默认运行配置
     */
    public static SettingsConfig defaultForTier(String tier) {
        return switch (tier) {
            case "free" -> new SettingsConfig("qwen-plus",
                    List.of("qwen-plus", "deepseek-chat"), 30, 5);
            case "standard" -> new SettingsConfig("qwen-plus",
                    List.of("qwen-plus", "deepseek-chat", "glm-4"), 60, 20);
            case "premium" -> new SettingsConfig("qwen-max",
                    List.of("qwen-max", "qwen-plus", "deepseek-chat", "glm-4"), 90, 30);
            case "enterprise" -> new SettingsConfig("qwen-max",
                    List.of("qwen-max", "qwen-plus", "deepseek-chat", "glm-4"), 90, 50);
            default -> defaultConfig();
        };
    }
}
