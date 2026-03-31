// 真实工具实现 - 替换 Mock

package com.platform.toolbus.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.toolbus.client.OrderServiceClient;
import com.platform.toolbus.dto.OrderInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * 订单查询工具
 *
 * 通过 OrderServiceClient 接口调用服务
 * 支持配置切换 Mock 和真实实现
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OrderQueryTool implements RealTool {

    private final ObjectMapper objectMapper;
    private final OrderServiceClient orderServiceClient;

    @Override
    public String getName() {
        return "query_order_status";
    }

    @Override
    public String getCategory() {
        return "query";
    }

    @Override
    public String getRiskLevel() {
        return "low";
    }

    @Override
    public String execute(Map<String, Object> arguments) {
        String orderId = (String) arguments.get("order_id");
        log.info("Querying order: {} (client={})",
            orderId, orderServiceClient.isRealService() ? "real" : "mock");

        OrderInfo order = orderServiceClient.getOrderInfo(orderId);

        if (order == null) {
            try {
                return objectMapper.writeValueAsString(Map.of(
                    "error", "order_not_found",
                    "order_id", orderId
                ));
            } catch (Exception e) {
                throw new RuntimeException("Failed to serialize error response", e);
            }
        }

        // 返回订单信息
        try {
            Map<String, Object> result = new HashMap<>();
            result.put("order_id", order.getOrderId());
            result.put("status", order.getStatus());
            result.put("amount", order.getAmount());
            result.put("items", order.getItems());
            result.put("delivery_address", maskAddress(order.getDeliveryAddress()));
            result.put("created_at", order.getCreatedAt());
            result.put("updated_at", order.getUpdatedAt());

            return objectMapper.writeValueAsString(result);
        } catch (Exception e) {
            throw new RuntimeException("Failed to serialize order info", e);
        }
    }

    private String maskAddress(String address) {
        if (address == null || address.length() < 10) {
            return address;
        }
        // 保留前缀，隐藏详细地址
        int maskStart = Math.min(6, address.length() / 2);
        return address.substring(0, maskStart) + "***";
    }
}
