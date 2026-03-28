package com.platform.toolbus.client.impl;

import com.platform.toolbus.client.PaymentGatewayClient;
import com.platform.toolbus.dto.PaymentResult;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

/**
 * Mock 支付网关客户端
 *
 * 当 external-services.payment.enabled=false 时启用
 */
@Slf4j
@Component
@ConditionalOnProperty(name = "external-services.payment.enabled", havingValue = "false", matchIfMissing = true)
public class MockPaymentGatewayClient implements PaymentGatewayClient {

    @Override
    public PaymentResult processPayment(String orderId, BigDecimal amount, String paymentMethod) {
        log.info("Mock: processing payment orderId={}, amount={}, method={}", orderId, amount, paymentMethod);

        // 返回模拟支付成功
        return new PaymentResult(
            "TXN-" + UUID.randomUUID().toString().substring(0, 8),
            orderId,
            amount,
            "success",
            paymentMethod,
            Instant.now().toString()
        );
    }

    @Override
    public boolean isRealService() {
        return false;
    }
}