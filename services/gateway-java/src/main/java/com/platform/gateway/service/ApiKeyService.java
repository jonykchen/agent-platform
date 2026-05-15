package com.platform.gateway.service;

import com.platform.gateway.entity.ApiKey;
import com.platform.gateway.entity.ApiKeyType;
import com.platform.gateway.repository.ApiKeyRepository;
import com.platform.gateway.security.ApiKeyPrincipal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * API Key 服务
 *
 * 【核心职责】
 * - 验证 API Key（SHA-256 哈希验证）
 * - 生成新的 API Key
 * - 管理权限范围
 *
 * 【安全原则】
 * - API Key 明文只显示一次（生成时）
 * - 数据库只存储哈希值
 * - 支持过期时间和禁用
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApiKeyService {

    private final ApiKeyRepository apiKeyRepository;

    private static final int PREFIX_LENGTH = 8;

    /**
     * 验证外部 API Key
     *
     * @param apiKey 明文 API Key
     * @return 认证主体，无效返回 null
     */
    @Transactional(readOnly = true)
    public ApiKeyPrincipal validateExternalKey(String apiKey) {
        if (apiKey == null || !apiKey.startsWith("ext_")) {
            return null;
        }

        // 计算哈希值
        String keyHash = hashApiKey(apiKey);
        String keyPrefix = apiKey.substring(0, Math.min(PREFIX_LENGTH, apiKey.length()));

        // 先按前缀快速查找
        var maybeKey = apiKeyRepository.findActiveByKeyHash(keyHash);

        if (maybeKey.isEmpty()) {
            // 回退到前缀查找
            maybeKey = apiKeyRepository.findValidByKeyPrefix(keyPrefix, Instant.now());
        }

        if (maybeKey.isEmpty()) {
            log.warn("API Key not found or inactive: prefix={}", keyPrefix);
            return null;
        }

        var key = maybeKey.get();

        // 双重验证：哈希值必须匹配
        if (!keyHash.equals(key.getKeyHash())) {
            log.warn("API Key hash mismatch: prefix={}", keyPrefix);
            return null;
        }

        // 检查是否有效
        if (!key.isValid()) {
            log.warn("API Key expired or disabled: prefix={}", keyPrefix);
            return null;
        }

        // 更新最后使用时间（异步）
        updateLastUsedAsync(key.getId());

        // 构建权限
        List<GrantedAuthority> authorities = key.getScopes().stream()
            .map(scope -> new SimpleGrantedAuthority("ROLE_" + scope.toUpperCase()))
            .collect(java.util.stream.Collectors.toList());

        return new ApiKeyPrincipal(
            key.getId().toString(),
            key.getUserId(),
            key.getTenantId(),
            authorities
        );
    }

    /**
     * 生成新的 API Key
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID（可选）
     * @param name 名称
     * @param scopes 权限范围
     * @param expiresAt 过期时间（可选）
     * @return 明文 API Key（只显示一次）
     */
    @Transactional
    public String generateApiKey(String tenantId, String userId, String name, List<String> scopes, Instant expiresAt) {
        // 生成随机部分
        String randomPart = UUID.randomUUID().toString().replace("-", "").substring(0, 24);

        // 确定前缀
        String prefix = ApiKeyType.EXTERNAL.getPrefix();
        String plainKey = prefix + randomPart;

        // 计算哈希和前缀
        String keyHash = hashApiKey(plainKey);
        String keyPrefix = plainKey.substring(0, PREFIX_LENGTH);

        // 创建实体
        ApiKey apiKey = ApiKey.builder()
            .keyHash(keyHash)
            .keyPrefix(keyPrefix)
            .tenantId(tenantId)
            .userId(userId)
            .name(name)
            .type(ApiKeyType.EXTERNAL)
            .scopes(scopes != null ? scopes.stream().collect(java.util.stream.Collectors.toSet()) : java.util.Collections.emptySet())
            .expiresAt(expiresAt)
            .isActive(true)
            .createdBy(userId)
            .build();

        apiKeyRepository.save(apiKey);

        log.info("API Key generated: tenant={}, name={}, prefix={}", tenantId, name, keyPrefix);

        return plainKey;
    }

    /**
     * 撤销 API Key
     */
    @Transactional
    public void revokeApiKey(UUID apiKeyId) {
        apiKeyRepository.findById(apiKeyId).ifPresent(key -> {
            key.setIsActive(false);
            apiKeyRepository.save(key);
            log.info("API Key revoked: id={}", apiKeyId);
        });
    }

    /**
     * 计算 API Key 的 SHA-256 哈希值
     */
    private String hashApiKey(String apiKey) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(apiKey.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new RuntimeException("SHA-256 algorithm not found", e);
        }
    }

    /**
     * 异步更新最后使用时间
     */
    private void updateLastUsedAsync(UUID apiKeyId) {
        // 简单实现：直接更新（可以优化为异步队列）
        try {
            apiKeyRepository.updateLastUsedAt(apiKeyId, Instant.now());
        } catch (Exception e) {
            log.warn("Failed to update last used time for API Key: {}", apiKeyId);
        }
    }
}
