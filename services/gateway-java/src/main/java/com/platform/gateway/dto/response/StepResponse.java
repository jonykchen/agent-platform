package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * Step 响应 DTO
 *
 * <p>用于返回 Agent 执行步骤的信息。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/sessions/{sessionId}/runs/{runId}/steps - 获取 Run 的所有步骤</li>
 * </ul>
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class StepResponse {

    /**
     * Step ID
     */
    private UUID id;

    /**
     * 步骤顺序
     */
    private Integer stepOrder;

    /**
     * 步骤类型
     * <p>可选值：thinking, tool_call, tool_result
     */
    private String stepType;

    /**
     * 步骤内容
     */
    private String content;

    /**
     * 工具名称（仅 tool_call 类型）
     */
    private String toolName;

    /**
     * 工具输入（JSON 格式，仅 tool_call 类型）
     */
    private String toolInput;

    /**
     * 工具输出（JSON 格式，仅 tool_result 类型）
     */
    private String toolOutput;

    /**
     * Token 数
     */
    private Integer tokenCount;

    /**
     * 执行时长（毫秒）
     */
    private Integer durationMs;

    /**
     * 创建时间
     */
    private Instant createdAt;
}
