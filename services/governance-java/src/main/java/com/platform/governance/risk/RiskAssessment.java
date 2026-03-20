package com.platform.governance.risk;

import lombok.Builder;
import lombok.Data;

import java.util.Map;

/**
 * 风险评估结果
 */
@Data
@Builder
public class RiskAssessment {

    private String toolName;
    private String tenantId;
    private String riskLevel;       // low / medium / high / critical
    private int riskScore;
    private String matchedRule;
    private boolean requiresApproval;
    private Map<String, Object> details;
}
