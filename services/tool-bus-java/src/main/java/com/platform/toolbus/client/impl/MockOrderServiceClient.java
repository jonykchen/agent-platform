package com.platform.toolbus.client.impl;

import com.platform.toolbus.client.OrderServiceClient;
import com.platform.toolbus.dto.OrderInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;

/**
 * Mock 订单服务客户端
 *
 * 当 external-services.order.enabled=false 时启用
 */
@Slf4j
@Component
@ConditionalOnProperty(name = "external-services.order.enabled", havingValue = "false", matchIfMissing = true)
public class MockOrderServiceClient implements OrderServiceClient {

    @Override
    public OrderInfo getOrderInfo(String orderId) {
        log.info("Mock: querying order {}", orderId);

        // 返回模拟数据
        return new OrderInfo(
            orderId,
            "delivered",
            BigDecimal.valueOf(299.00),
            3,
            "北京市朝阳区***",
            "2026-05-01T10:00:00Z",
            "2026-05-03T15:30:00Z"
        );
    }

    @Override
    public boolean isRealService() {
        return false;
    }
}