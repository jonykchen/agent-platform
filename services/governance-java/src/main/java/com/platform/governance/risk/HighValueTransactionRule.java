package com.platform.governance.risk;

import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 高金额交易规则 - 金额超过阈值需要审批
 *
 * 【业务场景】
 * 金融交易场景需要根据金额大小决定审批流程：
 * - 小额交易（< 10000）：自动通过，无需审批
 * - 大额交易（>= 10000）：需要审批，防止欺诈或误操作
 *
 * 【技术选型】阈值选择依据
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 阈值策略          │ 适用场景                    │ 优缺点                      │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 固定阈值 10000    │ • 标准化审批流程            │ 优点：简单一致，易于理解    │
 * │ (当前选择)        │ • 普通客服场景              │ 缺点：无法适应特殊业务      │
 * │                    │ • 小额高频交易              │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 租户级可配置阈值  │ • 多租户 SaaS               │ 优点：灵活适配不同客户      │
 * │                    │ • VIP 客户特殊待遇          │ 缺点：配置复杂，需校验      │
 * │                    │ • 不同行业监管要求          │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 动态风险评估      │ • 复杂金融场景              │ 优点：最智能，考虑上下文    │
 * │ (LLM 评估)        │ • 需考虑历史行为            │ 缺点：增加调用成本          │
 * │                    │                             │ • 可能引入不确定性          │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【选择固定阈值 10000 的原因】
 * 1. 客服场景金额分布：90% 操作 < 1000，10000 已覆盖大部分异常
 * 2. 审批效率：阈值过低会增加审批负担，影响用户体验
 * 3. 安全与效率平衡：10000 是行业标准阈值参考值
 *
 * 【后续优化方向】
 * - 支持租户级阈值配置（存储在 Redis）
 * - 支持按时间段动态调整（如夜间交易降低阈值）
 */
@Component
public class HighValueTransactionRule implements RiskRule {

    private static final double THRESHOLD = 10000.0;

    @Override
    public String getName() {
        return "high_value_transaction";
    }

    @Override
    public int getScore() {
        return 50;
    }

    @Override
    public boolean matches(String toolName, Map<String, Object> arguments, String tenantId) {
        if (!toolName.contains("payment") && !toolName.contains("transfer")) {
            return false;
        }

        Object amountObj = arguments.get("amount");
        if (amountObj instanceof Number) {
            double amount = ((Number) amountObj).doubleValue();
            return amount >= THRESHOLD;
        }

        return false;
    }
}
