"""真实工具实现 - 替换 Mock"""

package com.platform.toolbus.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 订单查询工具 - 真实实现
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class OrderQueryTool implements RealTool {

    private final ObjectMapper objectMapper;
    // private final OrderServiceClient orderServiceClient; // 注入真实服务客户端

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
        log.info("Querying order: {}", orderId);

        // TODO: 调用真实订单服务
        // Order order = orderServiceClient.getOrder(orderId);

        // Mock 返回（待替换为真实调用）
        try {
            return objectMapper.writeValueAsString(Map.of(
                "order_id", orderId,
                "status", "delivered",
                "amount", 299.00,
                "items", 3,
                "delivery_address", "北京市朝阳区***",
                "created_at", "2026-05-01T10:00:00Z",
                "updated_at", "2026-05-03T15:30:00Z"
            ));
        } catch (Exception e) {
            throw new RuntimeException("Failed to query order", e);
        }
    }
}
