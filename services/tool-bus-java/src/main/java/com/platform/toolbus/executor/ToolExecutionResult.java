package com.platform.toolbus.executor;

import lombok.Builder;
import lombok.Data;

/**
 * 工具执行结果
 */
@Data
@Builder
public class ToolExecutionResult {

    private String callId;
    private String status;          // pending / success / failed / rejected / pending_approval / timeout
    private String resultJson;
    private String approvalId;
    private String riskLevel;
    private boolean wasCached;
    private int durationMs;
    private int providerLatencyMs;
    private String errorCode;
    private String errorMessage;
}
