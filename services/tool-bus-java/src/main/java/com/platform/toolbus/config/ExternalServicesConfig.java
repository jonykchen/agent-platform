package com.platform.toolbus.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * 外部服务配置
 *
 * 支持通过配置切换 Mock 和真实服务
 *
 * 配置示例：
 * external-services:
 *   user:
 *     enabled: false    # false = Mock, true = 真实服务
 *     base-url: http://user-service:8080
 */
@Configuration
@ConfigurationProperties(prefix = "external-services")
@Data
public class ExternalServicesConfig {

    private UserService user = new UserService();
    private OrderService order = new OrderService();
    private PaymentGateway payment = new PaymentGateway();

    @Data
    public static class UserService {
        private boolean enabled = false;
        private String baseUrl = "http://user-service:8080";
        private int timeoutMs = 5000;
    }

    @Data
    public static class OrderService {
        private boolean enabled = false;
        private String baseUrl = "http://order-service:8080";
        private int timeoutMs = 5000;
    }

    @Data
    public static class PaymentGateway {
        private boolean enabled = false;
        private String baseUrl = "http://payment-gateway:8080";
        private int timeoutMs = 10000;
        private String merchantId;
        private String apiKey;
    }
}
