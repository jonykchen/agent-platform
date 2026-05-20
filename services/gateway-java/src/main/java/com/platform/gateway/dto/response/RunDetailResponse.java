package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * Run 详情响应 DTO
 *
 * <p>扩展 RunResponse，包含更多信息。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/sessions/{sessionId}/runs/{runId} - 获取单个 Run 详情</li>
 * </ul>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class RunDetailResponse {

    /**
     * Run ID
     */
    private UUID id;

    /**
     * 会话 ID
     */
    private UUID sessionId;

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

    /**
     * 错误码
     */
    private String errorCode;

    /**
     * 步骤数
     */
    private Integer stepCount;

    /**
     * 步骤列表（可选，仅在需要时返回）
     */
    private List<StepResponse> steps;
}
