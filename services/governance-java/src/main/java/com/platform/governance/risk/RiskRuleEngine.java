package com.platform.governance.risk;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

/**
 * 风险规则引擎
 * 评估工具调用风险等级，决定是否需要审批
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RiskRuleEngine {

    private final List<RiskRule> rules;

    /**
     * 评估风险等级
     */
    public RiskAssessment assess(String toolName, Map<String, Object> arguments, String tenantId) {
        int totalScore = 0;
        String matchedRule = null;

        for (RiskRule rule : rules) {
            if (rule.matches(toolName, arguments, tenantId)) {
                totalScore += rule.getScore();
                matchedRule = rule.getName();
                log.debug("Rule matched: {} for tool {}", rule.getName(), toolName);
            }
        }

        String riskLevel = calculateLevel(totalScore);
        boolean requiresApproval = totalScore >= 30 || isHighRiskTool(toolName);

        return RiskAssessment.builder()
                .toolName(toolName)
                .tenantId(tenantId)
                .riskLevel(riskLevel)
                .riskScore(totalScore)
                .matchedRule(matchedRule)
                .requiresApproval(requiresApproval)
                .build();
    }

    private String calculateLevel(int score) {
        if (score >= 80) return "critical";
        if (score >= 50) return "high";
        if (score >= 30) return "medium";
        return "low";
    }

    private boolean isHighRiskTool(String toolName) {
        return toolName.contains("delete") || toolName.contains("remove")
            || toolName.contains("payment") || toolName.contains("transfer");
    }
}
