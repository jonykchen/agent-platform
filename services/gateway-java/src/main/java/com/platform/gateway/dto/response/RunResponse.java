package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Run 响应 DTO
 *
 * <p>用于返回 Agent 运行实例的基本信息。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/sessions/{sessionId}/runs - 获取会话的 Run 列表</li>
 * </ul>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RunResponse {

    /**
     * Run ID
     */
    private UUID id;

    /**
     * 运行序号（会话内唯一）
     */
    private Integer runNumber;

    /**
     * 运行状态
     * <p>可选值：running, completed, failed, cancelled
     */
    private String status;

    /**
     * 输入消息
     */
    private String inputMessage;

    /**
     * 输出消息
     */
    private String outputMessage;

    /**
     * 使用的模型
     */
    private String modelUsed;

    /**
     * 总 Token 数
     */
    private Integer totalTokens;

    /**
     * 总成本（美元）
     */
    private BigDecimal totalCostUsd;

    /**
     * 执行时长（毫秒）
     */
    private Integer durationMs;

    /**
     * 开始时间
     */
    private Instant startedAt;

    /**
     * 完成时间
     */
    private Instant completedAt;

    /**
     * 错误消息
     */
    private String errorMessage;
}
