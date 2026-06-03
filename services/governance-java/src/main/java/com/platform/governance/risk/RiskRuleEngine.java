package com.platform.governance.risk;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 风险规则引擎
 * 评估工具调用风险等级，决定是否需要审批
 *
 * 【设计模式】责任链模式 (Chain of Responsibility)
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * 规则按顺序执行，每个规则可独立决定是否匹配：
 *
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          规则执行流程                                       │
 * │                                                                             │
 * │   输入: toolName, arguments, tenantId                                      │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  Rule 1: HighValueTransactionRule                                │    │
 * │   │  - 匹配条件: payment/transfer + amount >= 10000                 │    │
 * │   │  - 得分: 50                                                       │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  Rule 2: SensitiveFieldRule                                      │    │
 * │   │  - 匹配条件: 包含 password/credit_card/ssn                        │    │
 * │   │  - 得分: 40                                                       │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  Rule N: ...                                                      │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   汇总: totalScore, matchedRule → riskLevel → requiresApproval           │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *
 * 【技术选型】规则匹配方案对比
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 责任链遍历 (选择)  │ • 简单直观                  │ • 规则多时性能下降          │
 * │                    │ • 易于扩展                  │   （但本项目规则数 < 10）   │
 * │                    │ • 无额外依赖                │                              │
 * │                    │ • 每个规则可独立测试        │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Drools 规则引擎    │ • 复杂规则支持              │ • 重量级依赖                │
 * │                    │ • 声明式配置                │ • 学习曲线陡峭              │
 * │                    │ • 性能优化（Rete 算法）     │ • 调试困难                  │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 决策树             │ • 高效匹配                  │ • 规则变更需重建树          │
 * │                    │ • 可编译优化                │ • 复杂条件表达困难          │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【选择责任链遍历的原因】
 * 1. 本项目规则数量少（< 10），遍历性能足够
 * 2. 每个规则可独立单元测试，便于维护
 * 3. 无额外依赖，保持项目轻量
 * 4. 规则变更时只需增删实现类，无需修改引擎
 *
 * 【风险分数计算】
 * - 每个 Rule 返回一个分数（0-100）
 * - 总分 = 所有匹配规则的分数之和
 * - riskLevel = 分数区间映射：
 *   - score >= 80: critical
 *   - score >= 50: high
 *   - score >= 30: medium
 *   - score < 30: low
 *
 * 【审批触发条件】
 * - totalScore >= 30（medium 及以上）
 * - 或 isHighRiskTool(toolName) = true（包含 delete/payment/transfer）
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
        List<String> matchedRules = new ArrayList<>();

        for (RiskRule rule : rules) {
            if (rule.matches(toolName, arguments, tenantId)) {
                totalScore += rule.getScore();
                matchedRules.add(rule.getName());
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
                .matchedRule(String.join(",", matchedRules))
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
