package com.platform.gateway.util;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import jakarta.annotation.PostConstruct;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.stream.Collectors;

/**
 * JWT 工具类
 * 用于生成和验证 JWT Token
 *
 * 【核心概念】JWT 在多租户系统中的作用
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * JWT（JSON Web Token）是无状态认证标准：
 * - 用户登录后，服务器签发 JWT
 * - 后续请求携带 JWT，服务器验证签名
 * - 无需存储 Session，适合分布式系统
 *
 * 本项目 JWT 包含：
 * - userId: 用户唯一标识
 * - tenantId: 租户标识（多租户隔离）
 * - roles: 用户角色（RBAC）
 * - type: token 类型（access/refresh）
 *
 * 【技术选型】JWT 密钥管理方案
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 配置文件硬编码      │ • 开发简单                  │ • 不安全（明文可见）        │
 * │ (当前开发阶段)     │ • 无额外依赖                │ • 轮换需重启服务            │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 环境变量           │ • CI/CD 友好                │ • 明文可见                  │
 * │ (生产推荐)         │ • 无需配置文件              │ • 需运维配置                │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Vault/Secrets      │ • 安全加密存储              │ • 引入依赖                  │
 * │ Manager            │ • 动态轮换                  │ • 配置复杂                  │
 * │                    │                             │ • 增加延迟                  │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ JKS 密钥库         │ • Java 原生安全            │ • 管理复杂                  │
 * │                    │ • 支持非对称加密            │ • 密钥文件需保护            │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【生产环境建议】
 * 1. 使用环境变量存储密钥（AUTH_JWT_SECRET）
 * 2. 密钥长度 >= 256 bits（HS256 要求）
 * 3. 定期轮换密钥（建议 90 天）
 * 4. 使用 Vault 管理生产密钥
 *
 * 【Token 生命周期】
 * - Access Token: 3600 秒（1 小时）
 * - Refresh Token: 604800 秒（7 天）
 *
 * 【安全注意事项】
 * - 密钥必须足够长（>= 256 bits for HS256）
 * - Token 中不存储敏感信息（JWT 是 base64 编码，非加密）
 * - 验证 Token 时检查过期时间
 */
@Slf4j
@Component
public class JwtUtil {

    @Value("${auth.jwt.secret:your-secret-key-must-be-at-least-256-bits-long-for-hs256}")
    private String jwtSecret;

    @Value("${auth.jwt.access-token-ttl-seconds:3600}")
    private long accessTokenTtlSeconds;

    @Value("${auth.jwt.refresh-token-ttl-seconds:604800}")
    private long refreshTokenTtlSeconds;

    @Value("${spring.profiles.active:local}")
    private String activeProfile;

    /**
     * 已知的不安全默认密钥值，生产/预发环境禁止使用。
     */
    private static final Set<String> KNOWN_DEFAULT_SECRETS = Set.of(
        "your-secret-key-must-be-at-least-256-bits-long-for-hs256",
        "your-secret-key-must-be-at-least-256-bits-long-for-hs256-algorithm"
    );

    /**
     * 仅允许启用默认密钥的 profile 白名单。
     */
    private static final Set<String> SAFE_PROFILES = Set.of("local", "development", "default");

    /**
     * 启动时校验 JWT 密钥安全性。
     * 非 local/development 环境下使用已知默认密钥或过短密钥将拒绝启动。
     */
    @PostConstruct
    public void validateJwtSecret() {
        if (!SAFE_PROFILES.contains(activeProfile)) {
            if (KNOWN_DEFAULT_SECRETS.contains(jwtSecret)) {
                throw new IllegalStateException(
                    "FATAL: JWT secret is using a known default value in profile '" + activeProfile
                    + "'. Set JWT_SECRET environment variable.");
            }
            if (jwtSecret.length() < 32) {
                throw new IllegalStateException(
                    "FATAL: JWT secret must be at least 32 characters in profile '" + activeProfile
                    + "'. Current length: " + jwtSecret.length());
            }
        } else {
            log.warn("Using default JWT secret in development profile '{}'. "
                     + "This MUST be changed in production.", activeProfile);
        }
    }

    private SecretKey getSigningKey() {
        byte[] keyBytes = jwtSecret.getBytes(StandardCharsets.UTF_8);
        return Keys.hmacShaKeyFor(keyBytes);
    }

    /**
     * 生成 Access Token
     */
    public String generateAccessToken(String userId, String username, String tenantId, String[] roles) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("userId", userId);
        claims.put("tenantId", tenantId);
        claims.put("roles", roles);
        claims.put("type", "access");

        return Jwts.builder()
            .claims(claims)
            .subject(username)
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + accessTokenTtlSeconds * 1000))
            .signWith(getSigningKey())
            .compact();
    }

    /**
     * 生成 Refresh Token
     */
    public String generateRefreshToken(String userId, String username) {
        Map<String, Object> claims = new HashMap<>();
        claims.put("userId", userId);
        claims.put("type", "refresh");

        return Jwts.builder()
            .claims(claims)
            .subject(username)
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + refreshTokenTtlSeconds * 1000))
            .signWith(getSigningKey())
            .compact();
    }

    /**
     * 验证 Token 是否有效
     */
    public boolean validateToken(String token) {
        try {
            Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token);
            return true;
        } catch (Exception e) {
            log.warn("Token validation failed: {}", e.getMessage());
            return false;
        }
    }

    /**
     * 从 Token 中提取用户名
     */
    public String extractUsername(String token) {
        Claims claims = Jwts.parser()
            .verifyWith(getSigningKey())
            .build()
            .parseSignedClaims(token)
            .getPayload();
        return claims.getSubject();
    }

    /**
     * 从 Token 中提取用户 ID
     */
    public String extractUserId(String token) {
        Claims claims = Jwts.parser()
            .verifyWith(getSigningKey())
            .build()
            .parseSignedClaims(token)
            .getPayload();
        return claims.get("userId", String.class);
    }

    /**
     * 从 Token 中提取租户 ID
     */
    public String extractTenantId(String token) {
        Claims claims = Jwts.parser()
            .verifyWith(getSigningKey())
            .build()
            .parseSignedClaims(token)
            .getPayload();
        return claims.get("tenantId", String.class);
    }

    /**
     * 从 Token 中提取角色
     */
    public String[] extractRoles(String token) {
        Claims claims = Jwts.parser()
            .verifyWith(getSigningKey())
            .build()
            .parseSignedClaims(token)
            .getPayload();
        Object roles = claims.get("roles");
        if (roles instanceof String[] arr) {
            return arr;
        }
        // Jackson 反序列化 JSON 数组为 ArrayList 而非 String[]，需要兼容处理
        if (roles instanceof List<?> list) {
            return list.stream()
                .map(Object::toString)
                .toArray(String[]::new);
        }
        return new String[0];
    }

    /**
     * 检查 Token 是否过期
     */
    public boolean isTokenExpired(String token) {
        try {
            Claims claims = Jwts.parser()
                .verifyWith(getSigningKey())
                .build()
                .parseSignedClaims(token)
                .getPayload();
            return claims.getExpiration().before(new Date());
        } catch (Exception e) {
            return true;
        }
    }
}