// 真实工具实现 - 支付工具（高风险）

package com.platform.toolbus.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.toolbus.client.PaymentGatewayClient;
import com.platform.toolbus.dto.PaymentResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

/**
 * 支付工具 - 高风险，需要审批
 *
 * 通过 PaymentGatewayClient 接口调用服务
 * 支持配置切换 Mock 和真实实现
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PaymentTool implements RealTool {

    private final ObjectMapper objectMapper;
    private final PaymentGatewayClient paymentGatewayClient;

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
        Number amountNum = (Number) arguments.get("amount");
        String paymentMethod = (String) arguments.get("payment_method");

        BigDecimal amount = amountNum != null ? new BigDecimal(amountNum.toString()) : BigDecimal.ZERO;

        log.info("Processing payment: orderId={}, amount={}, method={} (client={})",
                orderId, amount, paymentMethod,
                paymentGatewayClient.isRealService() ? "real" : "mock");

        PaymentResult result = paymentGatewayClient.processPayment(orderId, amount, paymentMethod);

        // 返回支付结果
        try {
            Map<String, Object> response = new HashMap<>();
            response.put("transaction_id", result.getTransactionId());
            response.put("order_id", result.getOrderId());
            response.put("amount", result.getAmount());
            response.put("status", result.getStatus());
            response.put("payment_method", result.getPaymentMethod());
            response.put("processed_at", result.getProcessedAt());

            return objectMapper.writeValueAsString(response);
        } catch (Exception e) {
            throw new RuntimeException("Failed to serialize payment result", e);
        }
    }
}
