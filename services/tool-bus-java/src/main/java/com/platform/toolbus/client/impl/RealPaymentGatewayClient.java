package com.platform.toolbus.client.impl;

import com.platform.toolbus.client.PaymentGatewayClient;
import com.platform.toolbus.config.ExternalServicesConfig;
import com.platform.toolbus.dto.PaymentResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

import java.math.BigDecimal;

/**
 * 真实支付网关客户端
 *
 * 当 external-services.payment.enabled=true 时启用
 * 服务就绪后实现真实 HTTP 调用
 */
@Slf4j
@Component
@ConditionalOnProperty(name = "external-services.payment.enabled", havingValue = "true")
@RequiredArgsConstructor
public class RealPaymentGatewayClient implements PaymentGatewayClient {

    private final ExternalServicesConfig config;
    private final RestTemplate restTemplate;

    @Override
    public PaymentResult processPayment(String orderId, BigDecimal amount, String paymentMethod) {
        String url = config.getPayment().getBaseUrl() + "/api/v1/payments";

        log.info("Real: processing payment orderId={}, amount={} from {}", orderId, amount, url);

        // 注意：当前为 Mock 模式，生产环境需实现真实 HTTP 调用
        throw new UnsupportedOperationException("Real payment gateway not available yet. " +
            "Please ensure payment-gateway is running at " + config.getPayment().getBaseUrl());
    }

    @Override
    public boolean isRealService() {
        return true;
    }
}