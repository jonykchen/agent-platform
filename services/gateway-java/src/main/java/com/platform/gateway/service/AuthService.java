package com.platform.gateway.service;

import com.platform.gateway.dto.request.LoginRequest;
import com.platform.gateway.dto.request.RefreshTokenRequest;
import com.platform.gateway.dto.response.LoginResponse;
import com.platform.gateway.dto.response.RefreshTokenResponse;
import com.platform.gateway.entity.TenantUser;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.TenantUserRepository;
import com.platform.gateway.util.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 认证服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final JwtUtil jwtUtil;
    private final TenantUserRepository tenantUserRepository;
    private final UserService userService;
    private final PasswordEncoder passwordEncoder;

    @Value("${auth.jwt.access-token-ttl-seconds:3600}")
    private int accessTokenTtlSeconds;

    @Value("${auth.jwt.refresh-token-ttl-seconds:604800}")
    private int refreshTokenTtlSeconds; // 7天

    /** Token 存储用于登出和刷新 */
    private final Map<String, String> refreshTokenStore = new ConcurrentHashMap<>();

    // MVP: 权限映射
    private static final Map<String, String[]> ROLE_PERMISSIONS = Map.of(
        "admin", new String[]{"*"},
        "operator", new String[]{"chat:read", "chat:write", "approval:read", "approval:approve", "tools:execute"},
        "viewer", new String[]{"chat:read", "approval:read"}
    );

    // MVP: 租户信息（实际应从 Tenant 表查询）
    private static final Map<String, TenantInfo> TENANT_INFO = Map.of(
        "tenant_001", new TenantInfo("tenant_001", "示例企业", "enterprise")
    );

    /**
     * 用户登录
     */
    @Transactional
    public LoginResponse login(LoginRequest request) {
        // 查询用户（假设登录时使用 tenant_001）
        String tenantId = request.getTenantId() != null ? request.getTenantId() : "tenant_001";
        TenantUser user = tenantUserRepository.findByTenantIdAndUsernameForLogin(tenantId, request.getUsername())
            .orElse(null);

        // 验证用户存在
        if (user == null) {
            log.warn("Login failed: user not found, username={}", request.getUsername());
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "用户名或密码错误");
        }

        // 验证用户状态
        if (!"active".equals(user.getStatus())) {
            log.warn("Login failed: user disabled, userId={}", user.getUserId());
            throw new BusinessException(ErrorCode.ERR_USER_DISABLED, "用户已禁用");
        }

        // 验证密码
        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            // 增加登录失败计数
            userService.incrementFailedLoginCount(tenantId, user.getUserId());
            log.warn("Login failed: wrong password, username={}", request.getUsername());
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "用户名或密码错误");
        }

        // 获取用户角色和权限
        String[] roles = new String[]{user.getRole()};
        String[] permissions = ROLE_PERMISSIONS.getOrDefault(user.getRole(), new String[0]);

        // 生成 Token
        String accessToken = jwtUtil.generateAccessToken(user.getUserId(), user.getUsername(), tenantId, roles);
        String refreshToken = jwtUtil.generateRefreshToken(user.getUserId(), user.getUsername());

        // 存储 Refresh Token
        refreshTokenStore.put(refreshToken, user.getUserId());

        // 更新登录信息
        userService.updateLoginInfo(tenantId, user.getUserId(), null); // IP 可从请求获取

        // 构建 Token 信息
        LoginResponse.TokenInfo tokenInfo = LoginResponse.TokenInfo.builder()
            .accessToken(accessToken)
            .refreshToken(refreshToken)
            .expiresIn(accessTokenTtlSeconds)
            .tokenType("Bearer")
            .build();

        // 构建用户信息
        LoginResponse.UserInfo userInfo = LoginResponse.UserInfo.builder()
            .id(user.getUserId())
            .username(user.getUsername())
            .email(user.getEmail())
            .roles(roles)
            .permissions(permissions)
            .build();

        // 构建租户信息
        TenantInfo tenant = TENANT_INFO.getOrDefault(tenantId, new TenantInfo(tenantId, "默认租户", "basic"));
        LoginResponse.TenantInfo tenantInfo = LoginResponse.TenantInfo.builder()
            .id(tenant.id)
            .name(tenant.name)
            .tier(tenant.tier)
            .features(new String[]{"chat", "approval", "tools", "knowledge", "dashboard"})
            .build();

        log.info("User logged in: userId={}, username={}, tenantId={}", user.getUserId(), user.getUsername(), tenantId);

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
        String tenantId = jwtUtil.extractTenantId(refreshToken);

        TenantUser user = tenantUserRepository.findByTenantIdAndUsernameForLogin(tenantId, username)
            .orElseThrow(() -> new BusinessException(ErrorCode.ERR_USER_NOT_FOUND, "User not found"));

        // 验证用户状态
        if (!"active".equals(user.getStatus())) {
            throw new BusinessException(ErrorCode.ERR_USER_DISABLED, "用户已禁用");
        }

        // 使旧的 Refresh Token 失效
        refreshTokenStore.remove(refreshToken);

        // 获取用户角色
        String[] roles = new String[]{user.getRole()};

        // 生成新的 Token
        String newAccessToken = jwtUtil.generateAccessToken(user.getUserId(), user.getUsername(), tenantId, roles);
        String newRefreshToken = jwtUtil.generateRefreshToken(user.getUserId(), user.getUsername());

        // 存储新的 Refresh Token
        refreshTokenStore.put(newRefreshToken, user.getUserId());

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
    public void logout(String refreshToken) {
        if (refreshToken != null && refreshTokenStore.containsKey(refreshToken)) {
            refreshTokenStore.remove(refreshToken);
            log.info("User logged out, refresh token revoked");
        }
    }

    /**
     * 租户信息（MVP）
     */
    private static class TenantInfo {
        final String id;
        final String name;
        final String tier;

        TenantInfo(String id, String name, String tier) {
            this.id = id;
            this.name = name;
            this.tier = tier;
        }
    }
}