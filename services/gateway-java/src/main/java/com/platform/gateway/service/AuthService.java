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
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 认证服务
 *
 * <p>负责用户登录、Token 管理和权限验证，是 Gateway 的安全入口。
 *
 * <h3>核心概念：JWT 双 Token 机制</h3>
 *
 * <p>采用 Access Token + Refresh Token 双 Token 机制：
 * <ul>
 *   <li><b>Access Token</b>：短期有效（默认 1 小时），用于 API 认证</li>
 *   <li><b>Refresh Token</b>：长期有效（默认 7 天），用于刷新 Access Token</li>
 * </ul>
 *
 * <p>这种机制既保证了安全性（短 token 减少泄露风险），又提升了用户体验（无需频繁登录）。
 *
 * <h3>依赖关系</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          服务依赖关系                                        │
 * │                                                                             │
 * │   AuthController                                                            │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   AuthService ◄────────────────────────────────────────────────────────────│
 * │       │                                                                     │
 * │       ├──► JwtUtil (Token 生成和验证)                                       │
 * │       │                                                                     │
 * │       ├──► TenantUserRepository (用户数据查询)                              │
 * │       │                                                                     │
 * │       ├──► UserService (用户状态管理、登录信息更新)                         │
 * │       │                                                                     │
 * │       └──► PasswordEncoder (密码加密验证)                                    │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>技术选型：状态管理</h3>
 * <ul>
 *   <li><b>无状态 JWT</b>：Access Token 无状态，支持水平扩展</li>
 *   <li><b>有状态 Refresh Token</b>：存储在 Redis 中，支持主动撤销和多实例共享</li>
 *   <li><b>Redis</b>：分布式存储，支持 TTL 自动过期，多 Gateway 实例共享 Token 状态</li>
 * </ul>
 *
 * <h3>安全策略（S-AGENT-06 合规）</h3>
 * <ul>
 *   <li><b>密码加密</b>：BCrypt 单向加密，不可逆</li>
 *   <li><b>登录失败计数</b>：连续失败可触发账户锁定</li>
 *   <li><b>Token 撤销</b>：登出时从存储中移除 Refresh Token</li>
 *   <li><b>租户隔离</b>：Token 中包含租户信息，防止跨租户访问</li>
 * </ul>
 *
 * <h3>权限模型：RBAC</h3>
 *
 * <p>采用基于角色的访问控制（Role-Based Access Control）：
 * <pre>
 *   ┌──────────┬───────────────────────────────────────────────────┐
 *   │ Role     │ Permissions                                        │
 *   ├──────────┼───────────────────────────────────────────────────┤
 *   │ admin    │ * (全部权限)                                       │
 *   │ operator │ chat:read, chat:write, approval:read,             │
 *   │          │ approval:approve, tools:execute                   │
 *   │ viewer   │ chat:read, approval:read                          │
 *   └──────────┴───────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>设计模式：策略模式</h3>
 *
 * <p>权限验证采用策略模式，不同角色的权限集合由 {@link #ROLE_PERMISSIONS} 定义，
 * 便于后续扩展新的角色和权限组合。
 *
 * @see JwtUtil JWT 工具类
 * @see UserService 用户服务
 * @since 1.0.0
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final JwtUtil jwtUtil;
    private final TenantUserRepository tenantUserRepository;
    private final UserService userService;
    private final PasswordEncoder passwordEncoder;
    private final StringRedisTemplate redisTemplate;

    @Value("${auth.jwt.access-token-ttl-seconds:3600}")
    private int accessTokenTtlSeconds;

    @Value("${auth.jwt.refresh-token-ttl-seconds:604800}")
    private int refreshTokenTtlSeconds; // 7天

    /** Refresh Token Redis key 前缀 */
    private static final String REFRESH_TOKEN_KEY_PREFIX = "refresh_token:";

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
     *
     * <p>验证用户凭证，生成 JWT Token 并返回用户信息。
     * 这是 Gateway 的主入口点，所有需要认证的 API 调用都需要先登录获取 Token。
     *
     * <h4>处理流程</h4>
     * <ol>
     *   <li>查询用户（基于租户ID和用户名）</li>
     *   <li>验证用户存在性和状态</li>
     *   <li>验证密码（BCrypt 比对）</li>
     *   <li>生成 Access Token 和 Refresh Token</li>
     *   <li>存储 Refresh Token（支持撤销）</li>
     *   <li>更新用户登录信息（登录次数、最后登录时间）</li>
     *   <li>返回登录响应</li>
     * </ol>
     *
     * <h4>安全措施</h4>
     * <ul>
     *   <li><b>防暴力破解</b>：密码错误增加失败计数，可触发账户锁定</li>
     *   <li><b>防枚举攻击</b>：用户不存在和密码错误返回相同错误信息</li>
     *   <li><b>审计日志</b>：记录登录成功和失败事件</li>
     * </ul>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>用户状态必须为 active</li>
     *   <li>默认租户为 tenant_001（MVP 阶段）</li>
     *   <li>Access Token 有效期：{@link #accessTokenTtlSeconds}</li>
     *   <li>Refresh Token 有效期：{@link #refreshTokenTtlSeconds}</li>
     * </ul>
     *
     * @param request 登录请求，包含用户名、密码和可选的租户ID
     * @return 登录响应，包含用户信息、租户信息和 Token 信息
     * @throws BusinessException ERR_UNAUTHORIZED 用户名或密码错误
     * @throws BusinessException ERR_USER_DISABLED 用户已禁用
     * @since 1.0.0
     */
    @Transactional
    public LoginResponse login(LoginRequest request) {
        // 查询用户（默认租户）
        String tenantId = request.getTenantId() != null ? request.getTenantId() : "default";
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

        // 存储 Refresh Token 到 Redis（支持多实例共享，TTL 自动过期）
        redisTemplate.opsForValue().set(
            REFRESH_TOKEN_KEY_PREFIX + refreshToken,
            user.getUserId(),
            refreshTokenTtlSeconds,
            TimeUnit.SECONDS
        );

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
     *
     * <p>使用 Refresh Token 换取新的 Access Token 和 Refresh Token。
     * 这是 Token 续期的标准机制，避免用户频繁登录。
     *
     * <h4>处理流程</h4>
     * <ol>
     *   <li>验证 Refresh Token 格式有效性</li>
     *   <li>验证 Refresh Token 在存储中存在（未被撤销）</li>
     *   <li>解析 Token 获取用户信息</li>
     *   <li>验证用户状态</li>
     *   <li>使旧的 Refresh Token 失效</li>
     *   <li>生成新的 Access Token 和 Refresh Token</li>
     *   <li>返回新 Token</li>
     * </ol>
     *
     * <h4>安全措施</h4>
     * <ul>
     *   <li><b>单次使用</b>：每次刷新生成新的 Refresh Token，旧的立即失效</li>
     *   <li><b>主动撤销</b>：登出后 Refresh Token 从存储移除，无法刷新</li>
     *   <li><b>状态校验</b>：刷新时检查用户状态，禁用用户无法刷新</li>
     * </ul>
     *
     * @param request 刷新请求，包含有效的 Refresh Token
     * @return 刷新响应，包含新的 Access Token 和 Refresh Token
     * @throws BusinessException ERR_UNAUTHORIZED Refresh Token 无效或已撤销
     * @throws BusinessException ERR_USER_DISABLED 用户已禁用
     * @since 1.0.0
     */
    public RefreshTokenResponse refreshToken(RefreshTokenRequest request) {
        String refreshToken = request.getRefreshToken();

        // 验证 Refresh Token 格式
        if (!jwtUtil.validateToken(refreshToken)) {
            throw new BusinessException(ErrorCode.ERR_UNAUTHORIZED, "Invalid refresh token");
        }

        // 验证 Refresh Token 是否在 Redis 中
        String userId = redisTemplate.opsForValue().get(REFRESH_TOKEN_KEY_PREFIX + refreshToken);
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
        redisTemplate.delete(REFRESH_TOKEN_KEY_PREFIX + refreshToken);

        // 获取用户角色
        String[] roles = new String[]{user.getRole()};

        // 生成新的 Token
        String newAccessToken = jwtUtil.generateAccessToken(user.getUserId(), user.getUsername(), tenantId, roles);
        String newRefreshToken = jwtUtil.generateRefreshToken(user.getUserId(), user.getUsername());

        // 存储新的 Refresh Token 到 Redis
        redisTemplate.opsForValue().set(
            REFRESH_TOKEN_KEY_PREFIX + newRefreshToken,
            user.getUserId(),
            refreshTokenTtlSeconds,
            TimeUnit.SECONDS
        );

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
     *
     * <p>撤销用户的 Refresh Token，使其无法继续刷新 Access Token。
     * Access Token 会在过期前继续有效（JWT 无状态特性）。
     *
     * <h4>安全措施</h4>
     * <ul>
     *   <li><b>立即撤销</b>：Refresh Token 从存储中移除，无法刷新</li>
     *   <li><b>幂等性</b>：重复登出不报错</li>
     *   <li><b>审计日志</b>：记录登出事件</li>
     * </ul>
     *
     * <h4>注意事项</h4>
     * <p>登出后，Access Token 在过期前（默认 1 小时）仍然有效。
     * 如需立即失效，可考虑引入 Token 黑名单机制（需 Redis 支持）。
     *
     * @param refreshToken 要撤销的 Refresh Token
     * @since 1.0.0
     */
    public void logout(String refreshToken) {
        if (refreshToken != null) {
            Boolean deleted = redisTemplate.delete(REFRESH_TOKEN_KEY_PREFIX + refreshToken);
            if (Boolean.TRUE.equals(deleted)) {
                log.info("User logged out, refresh token revoked");
            }
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