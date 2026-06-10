package com.platform.toolbus.executor;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.toolbus.registry.ToolDefinition;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 工具风险闸门（审批闭环的强制执行点）
 *
 * <p>S-AGENT-06 五层鉴权的第 5 层（风险等级）在工具执行链路上的落地点。
 * 此前 Tool Bus 直接执行所有工具，高风险操作（支付/转账/删除）无任何拦截；
 * 本闸门在执行<b>之前</b>评估风险，对需要审批的工具返回
 * {@code pending_approval}，由编排层（LangGraph approval_wait 中断）转入
 * 人工审批流程，审批通过后再恢复执行。
 *
 * <p>【判定规则】（与 governance RiskRuleEngine 对齐，作为执行侧的本地强制）
 * <ol>
 *   <li>工具定义显式标注 {@code requiresApproval=true}</li>
 *   <li>风险等级为 high / critical</li>
 *   <li>工具名包含高风险关键词（delete/remove/payment/transfer/withdraw）</li>
 *   <li>写操作且金额超过阈值（{@value #AMOUNT_THRESHOLD}）</li>
 *   <li>参数包含敏感字段（password/credit_card/ssn/id_card）</li>
 * </ol>
 */
@Slf4j
@Component
public class ToolRiskGate {

    /** 金额审批阈值 */
    static final double AMOUNT_THRESHOLD = 10000.0;

    private static final Set<String> HIGH_RISK_KEYWORDS =
            Set.of("delete", "remove", "payment", "transfer", "withdraw");

    private static final Set<String> SENSITIVE_FIELDS =
            Set.of("password", "credit_card", "ssn", "id_card");

    private final ObjectMapper objectMapper;

    public ToolRiskGate(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    /**
     * 闸门判定结果。
     *
     * @param requiresApproval 是否需要审批
     * @param riskLevel        风险等级（low/medium/high/critical）
     * @param reason           需要审批的原因（requiresApproval=true 时有效）
     */
    public record Decision(boolean requiresApproval, String riskLevel, String reason) {}

    /**
     * 评估工具调用风险。
     *
     * @param tool          工具定义（可为 null，此时仅按工具名/参数判定）
     * @param toolName      工具名称
     * @param argumentsJson 参数 JSON
     * @return 风险判定结果
     */
    public Decision evaluate(ToolDefinition tool, String toolName, String argumentsJson) {
        // 规则 1/2：工具定义显式要求审批或高风险等级
        if (tool != null) {
            String level = tool.getRiskLevel();
            if (tool.isRequiresApproval()) {
                return new Decision(true, orDefault(level, "high"),
                        "工具定义要求审批: " + toolName);
            }
            if ("high".equals(level) || "critical".equals(level)) {
                return new Decision(true, level, "高风险工具等级: " + level);
            }
        }

        // 规则 3：高风险关键词
        String lowerName = toolName == null ? "" : toolName.toLowerCase();
        for (String kw : HIGH_RISK_KEYWORDS) {
            if (lowerName.contains(kw)) {
                return new Decision(true, "critical", "高风险关键词: " + kw);
            }
        }

        // 规则 4/5：金额阈值 / 敏感字段
        Map<String, Object> args = parseArgs(argumentsJson);
        if (args != null) {
            Object amountObj = args.get("amount");
            if (amountObj instanceof Number num && num.doubleValue() > AMOUNT_THRESHOLD) {
                return new Decision(true, "high",
                        "金额 " + num + " 超过阈值 " + AMOUNT_THRESHOLD);
            }
            for (String field : SENSITIVE_FIELDS) {
                if (args.containsKey(field)) {
                    return new Decision(true, "high", "涉及敏感字段: " + field);
                }
            }
        }

        // 无需审批：沿用工具定义风险等级，缺省 low
        String level = tool != null ? orDefault(tool.getRiskLevel(), "low") : "low";
        return new Decision(false, level, null);
    }

    /**
     * 构造 pending_approval 执行结果（生成 approvalId 供编排层关联）。
     */
    public ToolExecutionResult toPendingApproval(String callId, Decision decision) {
        String approvalId = "appr_" + UUID.randomUUID().toString().replace("-", "").substring(0, 20);
        log.info("Tool requires approval: approvalId={}, riskLevel={}, reason={}",
                approvalId, decision.riskLevel(), decision.reason());
        return ToolExecutionResult.builder()
                .callId(callId)
                .status("pending_approval")
                .approvalId(approvalId)
                .approvalReason(decision.reason())
                .riskLevel(decision.riskLevel())
                .build();
    }

    private Map<String, Object> parseArgs(String argumentsJson) {
        if (argumentsJson == null || argumentsJson.isBlank()) {
            return null;
        }
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> map = objectMapper.readValue(argumentsJson, Map.class);
            return map;
        } catch (Exception e) {
            log.warn("Failed to parse tool arguments for risk evaluation: {}", e.getMessage());
            return null;
        }
    }

    private static String orDefault(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }
}
