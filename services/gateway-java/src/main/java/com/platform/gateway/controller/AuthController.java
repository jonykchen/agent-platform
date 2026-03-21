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
 * 提供登录、刷新Token、登出接口
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    /**
     * 用户登录
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
     * 刷新Token
     */
    @PostMapping("/refresh")
    public ResponseEntity<?> refreshToken(@Valid @RequestBody RefreshTokenRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("Refresh token request: requestId={}", requestId);

        try {
            RefreshTokenResponse response = authService.refreshToken(request);
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
     */
    @PostMapping("/logout")
    public ResponseEntity<?> logout() {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Logout request: requestId={}", requestId);

        try {
            authService.logout();
            return ResponseEntity.ok().build();
        } catch (Exception e) {
            log.error("Logout error: requestId={}", requestId, e);
            // 登出失败不影响用户体验，返回成功
            return ResponseEntity.ok().build();
        }
    }
}