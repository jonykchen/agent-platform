"""真实工具实现 - 支付工具（高风险）"""

package com.platform.toolbus.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;

/**
 * 支付工具 - 高风险，需要审批
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PaymentTool implements RealTool {

    private final ObjectMapper objectMapper;

    @Override
    public String getName() {
        return "process_payment";
    }

    @Override
    public String getCategory() {
        return "write";
    }

    @Override
    public String getRiskLevel() {
        return "critical";
    }

    @Override
    public boolean requiresApproval() {
        return true;
    }

    @Override
    public String execute(Map<String, Object> arguments) {
        String orderId = (String) arguments.get("order_id");
        Number amount = (Number) arguments.get("amount");
        String paymentMethod = (String) arguments.get("payment_method");

        log.info("Processing payment: orderId={}, amount={}, method={}",
                orderId, amount, paymentMethod);

        // TODO: 调用真实支付网关
        try {
            return objectMapper.writeValueAsString(Map.of(
                "transaction_id", "TXN-" + UUID.randomUUID().toString().substring(0, 8),
                "order_id", orderId,
                "amount", amount,
                "status", "success",
                "payment_method", paymentMethod,
                "processed_at", java.time.Instant.now().toString()
            ));
        } catch (Exception e) {
            throw new RuntimeException("Failed to process payment", e);
        }
    }
}
