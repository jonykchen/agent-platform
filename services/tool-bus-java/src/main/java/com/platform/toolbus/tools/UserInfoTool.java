"""真实工具实现 - 用户信息查询"""

package com.platform.toolbus.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.toolbus.client.UserServiceClient;
import com.platform.toolbus.dto.UserInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.Map;

/**
 * 用户信息查询工具
 *
 * 通过 UserServiceClient 接口调用服务
 * 支持配置切换 Mock 和真实实现
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class UserInfoTool implements RealTool {

    private final ObjectMapper objectMapper;
    private final UserServiceClient userServiceClient;

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
        log.info("Querying user info: {} (client={})",
            userId, userServiceClient.isRealService() ? "real" : "mock");

        UserInfo user = userServiceClient.getUserInfo(userId);

        if (user == null) {
            try {
                return objectMapper.writeValueAsString(Map.of(
                    "error", "user_not_found",
                    "user_id", userId
                ));
            } catch (Exception e) {
                throw new RuntimeException("Failed to serialize error response", e);
            }
        }

        // 返回脱敏后的用户信息
        try {
            Map<String, Object> result = new HashMap<>();
            result.put("user_id", user.getId());
            result.put("name", user.getName());
            result.put("email", maskEmail(user.getEmail()));
            result.put("phone", maskPhone(user.getPhone()));
            result.put("level", user.getLevel());
            result.put("register_date", user.getRegisterDate());
            result.put("total_orders", user.getTotalOrders());

            return objectMapper.writeValueAsString(result);
        } catch (Exception e) {
            throw new RuntimeException("Failed to serialize user info", e);
        }
    }

    private String maskEmail(String email) {
        if (email == null || email.length() < 5) {
            return email;
        }
        int atIndex = email.indexOf("@");
        if (atIndex > 0) {
            return email.substring(0, Math.min(3, atIndex)) + "***" + email.substring(atIndex);
        }
        return email;
    }

    private String maskPhone(String phone) {
        if (phone == null || phone.length() < 7) {
            return phone;
        }
        return phone.substring(0, 3) + "****" + phone.substring(phone.length() - 4);
    }
}
