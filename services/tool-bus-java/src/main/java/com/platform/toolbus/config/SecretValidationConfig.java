package com.platform.toolbus.config;

import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;

import java.util.Set;

/**
 * 启动时校验敏感配置安全性。
 *
 * <p>非 local/development 环境下，如果关键密钥为空或使用已知弱密钥，服务将拒绝启动。
 * 这与 Orchestrator Python 服务的 config.py 校验逻辑保持一致。
 */
@Configuration
public class SecretValidationConfig {

    private static final Logger log = LoggerFactory.getLogger(SecretValidationConfig.class);

    private static final Set<String> UNSAFE_SECRETS = Set.of(
            "", "CHANGE_ME", "changeme", "password123"
    );

    private static final Set<String> SAFE_PROFILES = Set.of("local", "development", "default");

    @Value("${grpc.auth.secret:}")
    private String grpcAuthSecret;

    @Value("${spring.profiles.active:local}")
    private String activeProfile;

    @PostConstruct
    public void validateSecrets() {
        if (SAFE_PROFILES.contains(activeProfile)) {
            if (grpcAuthSecret.isEmpty()) {
                log.warn("⚠️ GRPC_AUTH_SECRET is empty in profile '{}'. "
                         + "Set GRPC_AUTH_SECRET for production.", activeProfile);
            }
            return;
        }

        // 生产/预发环境：强制校验
        if (UNSAFE_SECRETS.contains(grpcAuthSecret)) {
            throw new IllegalStateException(
                    "FATAL: GRPC_AUTH_SECRET is empty or using a default value in profile '"
                    + activeProfile + "'. Set GRPC_AUTH_SECRET environment variable.");
        }
        if (grpcAuthSecret.length() < 32) {
            throw new IllegalStateException(
                    "FATAL: GRPC_AUTH_SECRET must be at least 32 characters in profile '"
                    + activeProfile + "'. Current length: " + grpcAuthSecret.length());
        }

        log.info("✅ Secret validation passed for profile '{}'", activeProfile);
    }
}
