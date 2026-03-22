package com.platform.gateway.controller;

import com.platform.gateway.dto.request.CreateUserRequest;
import com.platform.gateway.dto.request.UpdateUserRequest;
import com.platform.gateway.dto.request.UserQueryParams;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.ResetPasswordResponse;
import com.platform.gateway.dto.response.UserDetailResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.service.UserService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * 用户管理控制器
 * 提供用户 CRUD、角色、权限查询接口
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final TenantContextService tenantContextService;

    /**
     * 获取用户列表
     * GET /api/v1/users
     */
    @GetMapping
    public ResponseEntity<PageResponse<UserDetailResponse>> getUsers(
        @ModelAttribute UserQueryParams params
    ) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("getUsers request: requestId={}, tenantId={}", requestId, tenantId);

        try {
            PageResponse<UserDetailResponse> response = userService.getUsers(tenantId, params);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("getUsers failed: requestId={}, error={}", requestId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("getUsers error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }

    /**
     * 创建用户
     * POST /api/v1/users
     */
    @PostMapping
    public ResponseEntity<UserDetailResponse> createUser(
        @Valid @RequestBody CreateUserRequest request
    ) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("createUser request: requestId={}, tenantId={}, username={}",
            requestId, tenantId, request.getUsername());

        try {
            UserDetailResponse response = userService.createUser(tenantId, request);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("createUser failed: requestId={}, error={}", requestId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("createUser error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }

    /**
     * 获取单个用户详情
     * GET /api/v1/users/{id}
     */
    @GetMapping("/{id}")
    public ResponseEntity<UserDetailResponse> getUser(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("getUser request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            UserDetailResponse response = userService.getUser(tenantId, userId);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("getUser failed: requestId={}, userId={}, error={}", requestId, userId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("getUser error: requestId={}, userId={}", requestId, userId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }

    /**
     * 更新用户
     * PATCH /api/v1/users/{id}
     */
    @PatchMapping("/{id}")
    public ResponseEntity<UserDetailResponse> updateUser(
        @PathVariable("id") String userId,
        @Valid @RequestBody UpdateUserRequest request
    ) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("updateUser request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            UserDetailResponse response = userService.updateUser(tenantId, userId, request);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("updateUser failed: requestId={}, userId={}, error={}", requestId, userId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("updateUser error: requestId={}, userId={}", requestId, userId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }

    /**
     * 禁用用户
     * POST /api/v1/users/{id}/disable
     */
    @PostMapping("/{id}/disable")
    public ResponseEntity<Void> disableUser(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("disableUser request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            userService.disableUser(tenantId, userId);
            return ResponseEntity.ok().build();
        } catch (BusinessException e) {
            log.warn("disableUser failed: requestId={}, userId={}, error={}", requestId, userId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("disableUser error: requestId={}, userId={}", requestId, userId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }

    /**
     * 启用用户
     * POST /api/v1/users/{id}/enable
     */
    @PostMapping("/{id}/enable")
    public ResponseEntity<Void> enableUser(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("enableUser request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            userService.enableUser(tenantId, userId);
            return ResponseEntity.ok().build();
        } catch (BusinessException e) {
            log.warn("enableUser failed: requestId={}, userId={}, error={}", requestId, userId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("enableUser error: requestId={}, userId={}", requestId, userId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }

    /**
     * 重置用户密码
     * POST /api/v1/users/{id}/reset-password
     */
    @PostMapping("/{id}/reset-password")
    public ResponseEntity<ResetPasswordResponse> resetPassword(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("resetPassword request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            ResetPasswordResponse response = userService.resetPassword(tenantId, userId);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("resetPassword failed: requestId={}, userId={}, error={}", requestId, userId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("resetPassword error: requestId={}, userId={}", requestId, userId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }
}
