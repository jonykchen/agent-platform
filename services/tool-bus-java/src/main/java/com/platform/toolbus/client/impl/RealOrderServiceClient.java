package com.platform.toolbus.client.impl;

import com.platform.toolbus.client.OrderServiceClient;
import com.platform.toolbus.config.ExternalServicesConfig;
import com.platform.toolbus.dto.OrderInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * 真实订单服务客户端
 *
 * 当 external-services.order.enabled=true 时启用
 * 服务就绪后实现真实 HTTP 调用
 */
@Slf4j
@Component
@ConditionalOnProperty(name = "external-services.order.enabled", havingValue = "true")
@RequiredArgsConstructor
public class RealOrderServiceClient implements OrderServiceClient {

    private final ExternalServicesConfig config;
    private final RestTemplate restTemplate;

    @Override
    public OrderInfo getOrderInfo(String orderId) {
        String url = config.getOrder().getBaseUrl() + "/api/v1/orders/" + orderId;

        log.info("Real: querying order {} from {}", orderId, url);

        // TODO: 实现真实 HTTP 调用，服务就绪后启用
        throw new UnsupportedOperationException("Real order service not available yet. " +
            "Please ensure order-service is running at " + config.getOrder().getBaseUrl());
    }

    @Override
    public boolean isRealService() {
        return true;
    }
}