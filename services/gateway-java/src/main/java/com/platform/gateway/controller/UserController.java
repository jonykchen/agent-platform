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
 *
 * 【核心职责】
 * 1. 提供用户 CRUD 操作（创建、查询、更新、禁用/启用）
 * 2. 管理用户密码重置功能
 * 3. 确保用户操作的租户隔离和审计追踪
 *
 * 【API 端点列表】
 * ┌──────────────────────────────────────────────────────────────────────────────┐
 * │ 方法   │ 路径                            │ 描述           │ 权限要求      │
 * ├────────┼─────────────────────────────────┼────────────────┼───────────────┤
 * │ GET    │ /api/v1/users                   │ 分页查询用户   │ user:read     │
 * │ POST   │ /api/v1/users                   │ 创建用户       │ user:write    │
 * │ GET    │ /api/v1/users/{id}              │ 获取用户详情   │ user:read    │
 * │ PATCH  │ /api/v1/users/{id}              │ 更新用户信息   │ user:write    │
 * │ POST   │ /api/v1/users/{id}/disable      │ 禁用用户       │ user:write    │
 * │ POST   │ /api/v1/users/{id}/enable       │ 启用用户       │ user:write    │
 * │ POST   │ /api/v1/users/{id}/reset-password│ 重置密码      │ user:write    │
 * └────────┴─────────────────────────────────┴────────────────┴───────────────┘
 *
 * 【技术选型】REST vs gRPC
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ REST (当前选择)    │ • 前端直接调用              │ • 无双向流式通信            │
 * │                    │ • 调试方便，工具支持好      │ • 高并发性能略低于 gRPC     │
 * │                    │ • 符合 S-JAVA-01            │                              │
 * │                    │ • HTTP PATCH 支持部分更新   │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ gRPC               │ • 高性能二进制协议          │ • 需要 Protocol Buffers     │
 * │                    │ • 双向流式通信              │ • 浏览器需 gRPC-Web 代理    │
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
 * │                    │ • @PatchMapping 支持完善   │                              │
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
 * 权限要求：
 * - user:read  - 查询用户信息
 * - user:write - 创建、更新、禁用/启用用户，重置密码
 *
 * 租户隔离：
 * - 所有操作自动注入 tenantId，确保数据隔离
 * - 用户只能看到和管理本租户内的用户
 * - 跨租户访问返回 404 NOT FOUND（不暴露其他租户存在性）
 *
 * 敏感数据处理：
 * - 密码在日志中脱敏（不记录明文）
 * - 重置密码返回的临时密码仅显示一次
 * - 用户列表返回时隐藏敏感字段（如密码哈希）
 *
 * 审计记录：
 * - 创建用户：记录 operatorId, createdUserId, username, createTime
 * - 更新用户：记录 operatorId, userId, changedFields, updateTime
 * - 禁用/启用：记录 operatorId, userId, action, actionTime
 * - 重置密码：记录 operatorId, userId, action, actionTime
 * - 审计日志不可删除或修改（符合 G-SEC-03）
 *
 * 【日志规范】
 * - INFO: 创建、更新、禁用/启用、重置密码操作
 * - DEBUG: 查询操作详情
 * - WARN: 业务异常（权限不足、数据不存在）
 * - ERROR: 系统异常
 * - 注意：日志中不记录密码、临时密码明文
 *
 * @see UserService
 * @see UserDetailResponse
 * @see TenantContextService
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
public class UserController {

    private final UserService userService;
    private final TenantContextService tenantContextService;

    /**
     * 分页查询用户列表
     *
     * 【功能说明】
     * 根据查询条件分页获取用户列表，支持按用户名、状态、角色等筛选。
     * 结果自动按租户隔离，只返回当前租户的用户。
     *
     * 【权限要求】
     * - user:read
     *
     * 【审计标记】
     * - 操作类型：QUERY
     * - 审计字段：tenantId, operatorId, queryConditions, resultCount
     *
     * @param params 查询参数，包含用户名、状态、分页信息等
     * @return 分页的用户列表
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
            log.info("getUsers success: requestId={}, total={}, page={}",
                    requestId, response.getTotal(), response.getPage());
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
     *
     * 【功能说明】
     * 在当前租户下创建新用户。系统会自动生成临时密码，
     * 并通过邮件或短信发送给用户（首次登录需修改密码）。
     *
     * 【权限要求】
     * - user:write
     *
     * 【数据校验】
     * - 用户名：必填，3-50 字符，仅允许字母、数字、下划线
     * - 邮箱：必填，符合邮箱格式，租户内唯一
     * - 手机号：选填，符合手机号格式
     * - 角色：必填，必须是有效角色 ID
     *
     * 【审计标记】
     * - 操作类型：CREATE
     * - 审计字段：tenantId, operatorId, createdUserId, username, createTime
     * - 重要：此操作会写入审计日志，不可删除
     *
     * @param request 创建用户请求，包含用户基本信息和角色
     * @return 创建成功的用户详情
     * @throws BusinessException 当用户名已存在、邮箱已存在或参数校验失败时抛出
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
            log.info("createUser success: requestId={}, userId={}, username={}",
                    requestId, response.getId(), response.getUsername());
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
     *
     * 【功能说明】
     * 根据用户 ID 获取用户的完整信息，包括基本信息、角色、权限等。
     * 仅返回当前租户内的用户，跨租户访问返回 404。
     *
     * 【权限要求】
     * - user:read
     *
     * 【审计标记】
     * - 操作类型：QUERY
     * - 审计字段：tenantId, operatorId, queriedUserId
     *
     * @param userId 用户 ID（UUID 格式）
     * @return 用户详情
     * @throws BusinessException 当用户不存在或不在当前租户时抛出
     */
    @GetMapping("/{id}")
    public ResponseEntity<UserDetailResponse> getUser(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("getUser request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            UserDetailResponse response = userService.getUser(tenantId, userId);
            log.info("getUser success: requestId={}, userId={}, username={}",
                    requestId, userId, response.getUsername());
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
     * 更新用户信息
     *
     * 【功能说明】
     * 部分更新用户信息（PATCH 语义）。仅更新请求中提供的字段，
     * 未提供的字段保持不变。支持更新邮箱、手机号、角色等。
     *
     * 【权限要求】
     * - user:write
     * - 不能修改自己的角色（防止权限提升）
     *
     * 【数据校验】
     * - 邮箱：若提供，需符合邮箱格式且租户内唯一
     * - 手机号：若提供，需符合手机号格式
     * - 角色：若提供，必须是有效角色 ID
     *
     * 【审计标记】
     * - 操作类型：UPDATE
     * - 审计字段：tenantId, operatorId, userId, changedFields, updateTime
     * - 重要：此操作会写入审计日志，不可删除
     *
     * @param userId 用户 ID（UUID 格式）
     * @param request 更新请求，仅包含需要更新的字段
     * @return 更新后的用户详情
     * @throws BusinessException 当用户不存在、邮箱已被占用或参数校验失败时抛出
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
            log.info("updateUser success: requestId={}, userId={}, username={}",
                    requestId, userId, response.getUsername());
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
     *
     * 【功能说明】
     * 禁用指定用户账户。禁用后该用户无法登录，所有 Token 立即失效。
     * 此操作可逆，可通过 enableUser 重新启用。
     *
     * 【权限要求】
     * - user:write
     * - 不能禁用自己（防止锁定所有管理员）
     * - 不能禁用租户管理员
     *
     * 【审计标记】
     * - 操作类型：DISABLE_USER
     * - 审计字段：tenantId, operatorId, targetUserId, actionTime
     * - 重要：此操作会写入审计日志，不可删除
     *
     * @param userId 用户 ID（UUID 格式）
     * @return 空响应（204 No Content 或 200 OK）
     * @throws BusinessException 当用户不存在、尝试禁用自己或禁用管理员时抛出
     */
    @PostMapping("/{id}/disable")
    public ResponseEntity<Void> disableUser(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("disableUser request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            userService.disableUser(tenantId, userId);
            log.info("disableUser success: requestId={}, userId={}", requestId, userId);
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
     *
     * 【功能说明】
     * 重新启用已禁用的用户账户。启用后该用户可正常登录。
     *
     * 【权限要求】
     * - user:write
     *
     * 【审计标记】
     * - 操作类型：ENABLE_USER
     * - 审计字段：tenantId, operatorId, targetUserId, actionTime
     * - 重要：此操作会写入审计日志，不可删除
     *
     * @param userId 用户 ID（UUID 格式）
     * @return 空响应（204 No Content 或 200 OK）
     * @throws BusinessException 当用户不存在时抛出
     */
    @PostMapping("/{id}/enable")
    public ResponseEntity<Void> enableUser(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("enableUser request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            userService.enableUser(tenantId, userId);
            log.info("enableUser success: requestId={}, userId={}", requestId, userId);
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
     *
     * 【功能说明】
     * 重置指定用户的密码。系统会生成临时密码，用户首次登录时需修改密码。
     * 临时密码通过邮件或短信发送给用户。
     *
     * 【权限要求】
     * - user:write
     * - 不能重置自己的密码（应使用个人设置中的修改密码功能）
     *
     * 【安全措施】
     * - 临时密码 24 小时内有效
     * - 首次登录强制修改密码
     * - 重置后所有现有 Token 立即失效
     * - 临时密码不在日志中记录
     *
     * 【审计标记】
     * - 操作类型：RESET_PASSWORD
     * - 审计字段：tenantId, operatorId, targetUserId, actionTime
     * - 重要：此操作会写入审计日志，不可删除
     * - 注意：临时密码不在日志中记录
     *
     * @param userId 用户 ID（UUID 格式）
     * @return 重置密码响应，包含临时密码信息
     * @throws BusinessException 当用户不存在或尝试重置自己密码时抛出
     */
    @PostMapping("/{id}/reset-password")
    public ResponseEntity<ResetPasswordResponse> resetPassword(@PathVariable("id") String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("resetPassword request: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        try {
            ResetPasswordResponse response = userService.resetPassword(tenantId, userId);
            log.info("resetPassword success: requestId={}, userId={}", requestId, userId);
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