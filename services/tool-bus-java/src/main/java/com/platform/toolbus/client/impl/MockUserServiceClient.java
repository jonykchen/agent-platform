package com.platform.toolbus.client.impl;

import com.platform.toolbus.client.UserServiceClient;
import com.platform.toolbus.dto.UserInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * Mock 用户服务客户端
 *
 * 当 external-services.user.enabled=false 时启用
 */
@Slf4j
@Component
@ConditionalOnProperty(name = "external-services.user.enabled", havingValue = "false", matchIfMissing = true)
public class MockUserServiceClient implements UserServiceClient {

    @Override
    public UserInfo getUserInfo(String userId) {
        log.info("Mock: querying user {}", userId);

        // 返回模拟数据
        return new UserInfo(
            userId,
            "张三",
            "zhang***@example.com",
            "138****5678",
            "gold",
            "2023-01-15",
            156
        );
    }

    @Override
    public boolean isRealService() {
        return false;
    }
}