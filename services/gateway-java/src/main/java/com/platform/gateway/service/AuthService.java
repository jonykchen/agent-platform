package com.platform.gateway.service;

import com.platform.gateway.dto.request.LoginRequest;
import com.platform.gateway.dto.request.RefreshTokenRequest;
import com.platform.gateway.dto.response.LoginResponse;
import com.platform.gateway.dto.response.RefreshTokenResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.util.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 认证服务
 *
 * MVP 阶段：使用内存存储用户数据，生产环境应替换为数据库
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final JwtUtil jwtUtil;

    @Value("${auth.jwt.access-token-ttl-seconds:3600}")
    private int accessTokenTtlSeconds;

    @Value("${auth.jwt.refresh-token-ttl-seconds:604800}")
    private int refreshTokenTtlSeconds; // 7天

    /** MVP: 内存用户存储 */
    private static final Map<String, MockUser> MOCK_USERS = new ConcurrentHashMap<>();

    /** MVP: Token 存储用于登出和刷新 */
    private final Map<String, String> refreshTokenStore = new ConcurrentHashMap<>();

    static {
        // 初始化 Mock 用户（生产环境从数据库读取）
        MOCK_USERS.put("admin", new MockUser(
            "user_001", "admin", "admin123", "admin@example.com",
            new String[]{"admin"}, new String[]{"*"},
            "tenant_001", "示例企业", "enterprise"
        ));
        MOCK_USERS.put("operator", new MockUser(
            "user_002", "operator", "operator123", "operator@example.com",
            new String[]{"operator"}, new String[]{"chat:read", "chat:write", "approval:read", "approval:approve"},
            "tenant_001", "示例企业", "enterprise"
        ));
        MOCK_USERS.put("viewer", new MockUser(
            "user_003", "viewer", "viewer123", "viewer@example.com",
            new String[]{"viewer"}, new String[]{"chat:read", "approval:read"},
            "tenant_001", "示例企业", "enterprise"
        ));
    }

    /**
     * 用户登录
     */
    public LoginResponse login(LoginRequest request) {
        MockUser user = MOCK_USERS.get(request.getUsername());

        // 验证用户存在
        if (user == null) {
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "用户名或密码错误");
        }

        // 验证密码
        if (!user.password.equals(request.getPassword())) {
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "用户名或密码错误");
        }

        // 生成 Token
        String accessToken = jwtUtil.generateAccessToken(user.userId, user.username, user.tenantId, user.roles);
        String refreshToken = jwtUtil.generateRefreshToken(user.userId, user.username);

        // 存储 Refresh Token
        refreshTokenStore.put(refreshToken, user.userId);

        // 构建 Token 信息
        Instant now = Instant.now();
        LoginResponse.TokenInfo tokenInfo = LoginResponse.TokenInfo.builder()
            .accessToken(accessToken)
            .refreshToken(refreshToken)
            .expiresIn(accessTokenTtlSeconds)
            .tokenType("Bearer")
            .build();

        // 构建用户信息
        LoginResponse.UserInfo userInfo = LoginResponse.UserInfo.builder()
            .id(user.userId)
            .username(user.username)
            .email(user.email)
            .roles(user.roles)
            .permissions(user.permissions)
            .build();

        // 构建租户信息
        LoginResponse.TenantInfo tenantInfo = LoginResponse.TenantInfo.builder()
            .id(user.tenantId)
            .name(user.tenantName)
            .tier(user.tenantTier)
            .features(new String[]{"chat", "approval", "tools", "knowledge", "dashboard"})
            .build();

        return LoginResponse.builder()
            .user(userInfo)
            .tenant(tenantInfo)
            .tokens(tokenInfo)
            .build();
    }

    /**
     * 刷新 Token
     */
    public RefreshTokenResponse refreshToken(RefreshTokenRequest request) {
        String refreshToken = request.getRefreshToken();

        // 验证 Refresh Token 格式
        if (!jwtUtil.validateToken(refreshToken)) {
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "Invalid refresh token");
        }

        // 验证 Refresh Token 是否在存储中
        String userId = refreshTokenStore.get(refreshToken);
        if (userId == null) {
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "Refresh token revoked or expired");
        }

        // 解析 Token 获取用户信息
        String username = jwtUtil.extractUsername(refreshToken);
        MockUser user = MOCK_USERS.get(username);
        if (user == null) {
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "User not found");
        }

        // 使旧的 Refresh Token 失效
        refreshTokenStore.remove(refreshToken);

        // 生成新的 Token
        String newAccessToken = jwtUtil.generateAccessToken(user.userId, user.username, user.tenantId, user.roles);
        String newRefreshToken = jwtUtil.generateRefreshToken(user.userId, user.username);

        // 存储新的 Refresh Token
        refreshTokenStore.put(newRefreshToken, user.userId);

        return RefreshTokenResponse.builder()
            .tokens(RefreshTokenResponse.TokenInfo.builder()
                .accessToken(newAccessToken)
                .refreshToken(newRefreshToken)
                .expiresIn(accessTokenTtlSeconds)
                .tokenType("Bearer")
                .build())
            .build();
    }

    /**
     * 登出
     */
    public void logout() {
        // MVP: 登出时清除该用户的所有 Refresh Token
        // 生产环境应从请求头获取当前用户的 Token 并使失效
        log.info("User logged out");
    }

    /**
     * Mock 用户数据
     */
    private static class MockUser {
        final String userId;
        final String username;
        final String password;
        final String email;
        final String[] roles;
        final String[] permissions;
        final String tenantId;
        final String tenantName;
        final String tenantTier;

        MockUser(String userId, String username, String password, String email,
                 String[] roles, String[] permissions,
                 String tenantId, String tenantName, String tenantTier) {
            this.userId = userId;
            this.username = username;
            this.password = password;
            this.email = email;
            this.roles = roles;
            this.permissions = permissions;
            this.tenantId = tenantId;
            this.tenantName = tenantName;
            this.tenantTier = tenantTier;
        }
    }
}