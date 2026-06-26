package com.platform.toolbus.client.impl;

import com.platform.toolbus.client.UserServiceClient;
import com.platform.toolbus.config.ExternalServicesConfig;
import com.platform.toolbus.dto.UserInfo;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;

/**
 * 真实用户服务客户端
 *
 * 当 external-services.user.enabled=true 时启用
 * 服务就绪后实现真实 HTTP 调用
 */
@Slf4j
@Component
@ConditionalOnProperty(name = "external-services.user.enabled", havingValue = "true")
@RequiredArgsConstructor
public class RealUserServiceClient implements UserServiceClient {

    private final ExternalServicesConfig config;
    private final RestTemplate restTemplate;

    @Override
    public UserInfo getUserInfo(String userId) {
        String url = config.getUser().getBaseUrl() + "/api/v1/users/" + userId;

        log.info("Real: querying user {} from {}", userId, url);

        // 注意：当前为 Mock 模式，生产环境需实现真实 HTTP 调用
        // 目前抛出异常，提示服务未就绪
        throw new UnsupportedOperationException("Real user service not available yet. " +
            "Please ensure user-service is running at " + config.getUser().getBaseUrl());
    }

    @Override
    public boolean isRealService() {
        return true;
    }
}