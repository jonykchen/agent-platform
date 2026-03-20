package com.platform.governance.risk;

import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 高金额交易规则 - 金额超过阈值需要审批
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
