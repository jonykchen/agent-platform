package com.platform.gateway.dto.response;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 可用模型响应 DTO
 *
 * <p>返回平台支持的所有可用模型列表。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/tenants/models - 获取可用模型列表</li>
 * </ul>
 *
 * <p>【权限要求】无需权限（公开接口）
 *
 * @see com.platform.gateway.controller.TenantController#getAvailableModels
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ModelResponse {

    /**
     * 模型ID
     *
     * <p>模型的唯一标识符。
     *
     * <p>【格式】如 "qwen-max", "deepseek-chat"
     */
    private String id;

    /**
     * 模型显示名称
     */
    private String name;

    /**
     * 模型提供商
     *
     * <p>【可选值】qwen（通义千问）、deepseek（深度求索）、zhipu（智谱）等
     */
    private String provider;

    /**
     * 模型类型
     *
     * <p>【可选值】chat（对话）、embedding（向量化）、rerank（重排序）
     */
    private String type;

    /**
     * 上下文窗口大小（Token 数）
     */
    @JsonProperty("context_window")
    private Integer contextWindow;

    /**
     * 最大输出 Token 数
     */
    @JsonProperty("max_output_tokens")
    private Integer maxOutputTokens;

    /**
     * 支持的功能
     *
     * <p>如：["function_call", "streaming", "vision"]
     */
    private List<String> capabilities;

    /**
     * 模型描述
     */
    private String description;

    /**
     * 是否启用
     */
    private Boolean enabled;

    /**
     * 排序权重
     */
    private Integer order;
}
