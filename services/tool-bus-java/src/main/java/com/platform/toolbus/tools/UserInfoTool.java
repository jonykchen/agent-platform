"""真实工具实现 - 用户信息查询"""

package com.platform.toolbus.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 用户信息查询工具 - 真实实现
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class UserInfoTool implements RealTool {

    private final ObjectMapper objectMapper;

    @Override
    public String getName() {
        return "get_user_info";
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
        String userId = (String) arguments.get("user_id");
        log.info("Querying user info: {}", userId);

        // TODO: 调用真实用户服务
        try {
            return objectMapper.writeValueAsString(Map.of(
                "user_id", userId,
                "name", "张三",
                "email", "zhang***@example.com",
                "phone", "138****5678",
                "level", "gold",
                "register_date", "2023-01-15",
                "total_orders", 156
            ));
        } catch (Exception e) {
            throw new RuntimeException("Failed to query user info", e);
        }
    }
}
