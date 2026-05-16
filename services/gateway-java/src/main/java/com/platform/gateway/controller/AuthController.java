package com.platform.gateway.controller;

import com.platform.gateway.dto.request.LoginRequest;
import com.platform.gateway.dto.request.RefreshTokenRequest;
import com.platform.gateway.dto.response.LoginResponse;
import com.platform.gateway.dto.response.RefreshTokenResponse;
import com.platform.gateway.dto.response.ErrorResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.AuthService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 认证控制器
 *
 * 【核心职责】
 * 1. 提供用户身份认证入口（登录/登出）
 * 2. 管理 Token 生命周期（刷新/撤销）
 * 3. 确保认证操作的安全性和审计追踪
 *
 * 【API 端点列表】
 * ┌──────────────────────────────────────────────────────────────────────────────┐
 * │ 方法   │ 路径                    │ 描述              │ 权限要求           │
 * ├────────┼─────────────────────────┼───────────────────┼────────────────────┤
 * │ POST   │ /api/v1/auth/login      │ 用户登录          │ 无（公开接口）     │
 * │ POST   │ /api/v1/auth/refresh    │ 刷新访问令牌      │ 有效 Refresh Token │
 * │ POST   │ /api/v1/auth/logout     │ 用户登出          │ 无（可选 Token）   │
 * └────────┴─────────────────────────┴───────────────────┴────────────────────┘
 *
 * 【技术选型】REST vs gRPC
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ REST (当前选择)    │ • 前端直接调用，无需代理    │ • 无双向流式通信            │
 * │                    │ • OAuth/OIDC 标准协议兼容   │ • 高并发性能略低于 gRPC     │
 * │                    │ • 符合 S-JAVA-01            │                              │
 * │                    │ • 无需 Protocol Buffers     │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ gRPC               │ • 高性能二进制协议          │ • 浏览器需 gRPC-Web 代理    │
 * │                    │ • 双向流式通信              │ • OAuth 集成复杂            │
 * │                    │ • 强类型契约                │ • 调试困难                  │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【技术选型】Spring MVC vs WebFlux
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Spring MVC (选择)  │ • 团队熟悉度高              │ • 线程阻塞模型              │
 * │                    │ • 生态成熟，调试方便        │ • 高并发需更多线程资源      │
 * │                    │ • Spring Security 集成简单  │                              │
 * │                    │ • 符合 S-JAVA-01            │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ WebFlux            │ • 非阻塞，高并发性能        │ • 学习曲线陡峭              │
 * │                    │ • 背压支持                   │ • 调试困难                  │
 * │                    │ • 更少线程资源              │ • 需要全链路响应式改造       │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【安全说明】
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * 认证机制：
 * - JWT Access Token：有效期 15 分钟，用于 API 访问
 * - JWT Refresh Token：有效期 7 天，用于刷新 Access Token
 * - Token 存储在 Redis 中，支持主动撤销
 *
 * 密码安全：
 * - 登录失败不区分"用户不存在"和"密码错误"，统一返回"用户名或密码错误"
 * - 密码使用 BCrypt 加密存储
 * - 连续登录失败触发账户锁定（由 AuthService 实现）
 *
 * 审计记录：
 * - 登录成功：记录 userId, tenantId, 登录时间, 客户端 IP
 * - 登录失败：记录 username, 失败原因, 客户端 IP
 * - Token 刷新：记录 userId, 刷新时间
 * - 登出：记录 userId, 登出时间
 *
 * 【日志规范】
 * - INFO: 登录成功、登出操作
 * - DEBUG: Token 刷新请求
 * - WARN: 登录失败、Token 刷新失败
 * - ERROR: 系统异常
 * - 注意：日志中不记录密码、Token 明文
 *
 * @see AuthService
 * @see LoginRequest
 * @see LoginResponse
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    /**
     * 用户登录
     *
     * 【功能说明】
     * 验证用户凭据（用户名/密码），成功后返回 Access Token 和 Refresh Token。
     * 同时返回用户基本信息和所属租户信息，供前端初始化使用。
     *
     * 【权限要求】
     * - 无（公开接口）
     *
     * 【安全措施】
     * - 登录失败不区分"用户不存在"和"密码错误"
     * - 连续失败触发账户锁定
     * - 密码在日志中脱敏
     *
     * 【审计标记】
     * - 操作类型：LOGIN
     * - 审计字段：username, userId, tenantId, loginTime, clientIp
     * - 失败场景：记录 username, failureReason, clientIp
     *
     * @param request 登录请求，包含用户名和密码
     * @return 登录响应，包含 Token、用户信息、租户信息
     * @throws BusinessException 当凭据无效、账户锁定或系统异常时抛出
     */
    @PostMapping("/login")
    public ResponseEntity<?> login(@Valid @RequestBody LoginRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Login request: requestId={}, username={}", requestId, request.getUsername());

        try {
            LoginResponse response = authService.login(request);
            log.info("Login success: requestId={}, userId={}, tenantId={}",
                    requestId, response.getUser().getId(), response.getTenant().getId());
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("Login failed: requestId={}, username={}, error={}",
                    requestId, request.getUsername(), e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("Login error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Authentication service unavailable");
        }
    }

    /**
     * 刷新访问令牌
     *
     * 【功能说明】
     * 使用有效的 Refresh Token 获取新的 Access Token。
     * 当 Access Token 过期时，前端应调用此接口无感刷新，无需重新登录。
     *
     * 【权限要求】
     * - 有效的 Refresh Token
     * - Refresh Token 未被撤销
     *
     * 【Token 刷新策略】
     * - 仅刷新 Access Token，Refresh Token 保持不变
     * - 若 Refresh Token 即将过期（< 1 天），同时返回新的 Refresh Token
     * - 旧的 Refresh Token 立即失效
     *
     * 【审计标记】
     * - 操作类型：TOKEN_REFRESH
     * - 审计字段：userId, refreshTokenId（脱敏）, refreshTime
     * - 失败场景：记录 failureReason
     *
     * @param request 刷新令牌请求，包含有效的 Refresh Token
     * @return 新的 Access Token 和（可选）新的 Refresh Token
     * @throws BusinessException 当 Refresh Token 无效、过期或已撤销时抛出
     */
    @PostMapping("/refresh")
    public ResponseEntity<?> refreshToken(@Valid @RequestBody RefreshTokenRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("Refresh token request: requestId={}", requestId);

        try {
            RefreshTokenResponse response = authService.refreshToken(request);
            log.info("Token refresh success: requestId={}, userId={}", requestId, response.getUserId());
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("Token refresh failed: requestId={}, error={}", requestId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("Token refresh error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Token refresh failed");
        }
    }

    /**
     * 用户登出
     *
     * 【功能说明】
     * 撤销用户的 Refresh Token，使其无法再刷新 Access Token。
     * Access Token 在过期前仍然有效（JWT 无状态特性），建议前端同时清除本地存储的 Token。
     *
     * 【权限要求】
     * - 无（可选提供 Refresh Token）
     *
     * 【登出策略】
     * - 若提供 Refresh Token：撤销该 Token
     * - 若不提供 Refresh Token：仅记录登出事件，不撤销任何 Token
     * - 登出失败不影响用户体验，始终返回成功
     *
     * 【审计标记】
     * - 操作类型：LOGOUT
     * - 审计字段：userId（从 Token 解析）, logoutTime
     *
     * @param request 登出请求，可选包含 Refresh Token
     * @return 空响应，始终返回 200 OK
     */
    @PostMapping("/logout")
    public ResponseEntity<?> logout(@RequestBody(required = false) RefreshTokenRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Logout request: requestId={}", requestId);

        try {
            String refreshToken = request != null ? request.getRefreshToken() : null;
            authService.logout(refreshToken);
            log.info("Logout success: requestId={}", requestId);
            return ResponseEntity.ok().build();
        } catch (Exception e) {
            log.error("Logout error: requestId={}", requestId, e);
            // 登出失败不影响用户体验，返回成功
            return ResponseEntity.ok().build();
        }
    }
}