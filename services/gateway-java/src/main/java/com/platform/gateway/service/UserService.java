package com.platform.gateway.service;

import com.platform.gateway.dto.request.CreateUserRequest;
import com.platform.gateway.dto.request.UpdateUserRequest;
import com.platform.gateway.dto.request.UserQueryParams;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.PermissionResponse;
import com.platform.gateway.dto.response.ResetPasswordResponse;
import com.platform.gateway.dto.response.RoleResponse;
import com.platform.gateway.dto.response.UserDetailResponse;
import com.platform.gateway.entity.TenantUser;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.TenantUserRepository;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.security.SecureRandom;
import java.time.Instant;
import java.util.List;

/**
 * 用户管理服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserService {

    private final TenantUserRepository tenantUserRepository;
    private final PasswordEncoder passwordEncoder;

    // MVP: 权限映射
    private static final java.util.Map<String, String[]> ROLE_PERMISSIONS = java.util.Map.of(
        "admin", new String[]{"*"},
        "operator", new String[]{"chat:read", "chat:write", "approval:read", "approval:approve", "tools:execute"},
        "viewer", new String[]{"chat:read", "approval:read"}
    );

    // MVP: 角色描述
    private static final java.util.Map<String, String> ROLE_DESCRIPTIONS = java.util.Map.of(
        "admin", "系统管理员，拥有全部权限",
        "operator", "操作员，可执行工具和审批",
        "viewer", "观察者，只读权限"
    );

    // MVP: 权限列表
    private static final List<PermissionInfo> PERMISSIONS = List.of(
        new PermissionInfo("chat:read", "查看对话", "chat"),
        new PermissionInfo("chat:write", "发送消息", "chat"),
        new PermissionInfo("approval:read", "查看审批", "approval"),
        new PermissionInfo("approval:approve", "审批操作", "approval"),
        new PermissionInfo("tools:execute", "执行工具", "tools"),
        new PermissionInfo("user:read", "查看用户", "user"),
        new PermissionInfo("user:write", "管理用户", "user"),
        new PermissionInfo("tenant:read", "查看租户", "tenant"),
        new PermissionInfo("tenant:write", "管理租户", "tenant"),
        new PermissionInfo("*", "全部权限", "system")
    );

    /**
     * 获取用户列表
     */
    public PageResponse<UserDetailResponse> getUsers(String tenantId, UserQueryParams params) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("getUsers: requestId={}, tenantId={}, params={}", requestId, tenantId, params);

        // 构建分页和排序
        Sort sort = buildSort(params.getSortBy(), params.getSortDescending());
        Pageable pageable = PageRequest.of(params.getPageNumber() - 1, params.getPageSize(), sort);

        // 查询数据
        Page<TenantUser> page = tenantUserRepository.findByConditions(
            tenantId,
            params.getStatus(),
            params.getRole(),
            pageable
        );

        // 转换响应
        List<UserDetailResponse> items = page.getContent().stream()
            .map(this::toUserDetailResponse)
            .toList();

        return PageResponse.<UserDetailResponse>builder()
            .items(items)
            .totalCount(page.getTotalElements())
            .pageNumber(params.getPageNumber())
            .totalPages(page.getTotalPages())
            .hasNext(page.hasNext())
            .build();
    }

    /**
     * 获取单个用户详情
     */
    public UserDetailResponse getUser(String tenantId, String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("getUser: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        TenantUser user = tenantUserRepository.findByTenantIdAndUserId(tenantId, userId)
            .orElseThrow(() -> new BusinessException(ErrorCode.ERR_USER_NOT_FOUND));

        return toUserDetailResponse(user);
    }

    /**
     * 创建用户
     */
    @Transactional
    public UserDetailResponse createUser(String tenantId, CreateUserRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("createUser: requestId={}, tenantId={}, username={}", requestId, tenantId, request.getUsername());

        // 检查用户名是否已存在
        if (tenantUserRepository.existsByTenantIdAndUsername(tenantId, request.getUsername())) {
            throw new BusinessException(ErrorCode.ERR_USER_ALREADY_EXISTS);
        }

        // 创建用户
        String userId = generateUserId();
        String hashedPassword = passwordEncoder.encode(request.getPassword());
        String primaryRole = request.getRoles()[0]; // 主角色

        TenantUser user = TenantUser.builder()
            .tenantId(tenantId)
            .userId(userId)
            .username(request.getUsername())
            .email(request.getEmail())
            .password(hashedPassword)
            .role(primaryRole)
            .status("active")
            .quotaDaily(100000)
            .quotaUsedToday(0)
            .loginCount(0)
            .failedLoginCount(0)
            .build();

        user = tenantUserRepository.save(user);
        log.info("User created: requestId={}, userId={}, username={}", requestId, userId, request.getUsername());

        return toUserDetailResponse(user);
    }

    /**
     * 更新用户
     */
    @Transactional
    public UserDetailResponse updateUser(String tenantId, String userId, UpdateUserRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("updateUser: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        TenantUser user = tenantUserRepository.findByTenantIdAndUserId(tenantId, userId)
            .orElseThrow(() -> new BusinessException(ErrorCode.ERR_USER_NOT_FOUND));

        // 更新用户名（需要检查唯一性）
        if (request.getUsername() != null && !request.getUsername().equals(user.getUsername())) {
            if (tenantUserRepository.existsByTenantIdAndUsername(tenantId, request.getUsername())) {
                throw new BusinessException(ErrorCode.ERR_USER_ALREADY_EXISTS);
            }
            user.setUsername(request.getUsername());
        }

        // 更新邮箱
        if (request.getEmail() != null) {
            user.setEmail(request.getEmail());
        }

        // 更新角色
        if (request.getRoles() != null && request.getRoles().length > 0) {
            user.setRole(request.getRoles()[0]);
        }

        // 更新状态
        if (request.getStatus() != null) {
            user.setStatus(request.getStatus());
        }

        user = tenantUserRepository.save(user);
        log.info("User updated: requestId={}, userId={}", requestId, userId);

        return toUserDetailResponse(user);
    }

    /**
     * 禁用用户
     */
    @Transactional
    public void disableUser(String tenantId, String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("disableUser: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        TenantUser user = tenantUserRepository.findByTenantIdAndUserId(tenantId, userId)
            .orElseThrow(() -> new BusinessException(ErrorCode.ERR_USER_NOT_FOUND));

        user.setStatus("inactive");
        tenantUserRepository.save(user);

        log.info("User disabled: requestId={}, userId={}", requestId, userId);
    }

    /**
     * 启用用户
     */
    @Transactional
    public void enableUser(String tenantId, String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("enableUser: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        TenantUser user = tenantUserRepository.findByTenantIdAndUserId(tenantId, userId)
            .orElseThrow(() -> new BusinessException(ErrorCode.ERR_USER_NOT_FOUND));

        user.setStatus("active");
        tenantUserRepository.save(user);

        log.info("User enabled: requestId={}, userId={}", requestId, userId);
    }

    /**
     * 重置密码
     */
    @Transactional
    public ResetPasswordResponse resetPassword(String tenantId, String userId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("resetPassword: requestId={}, tenantId={}, userId={}", requestId, tenantId, userId);

        TenantUser user = tenantUserRepository.findByTenantIdAndUserId(tenantId, userId)
            .orElseThrow(() -> new BusinessException(ErrorCode.ERR_USER_NOT_FOUND));

        // 生成临时密码
        String temporaryPassword = generateTemporaryPassword();
        String hashedPassword = passwordEncoder.encode(temporaryPassword);
        user.setPassword(hashedPassword);
        tenantUserRepository.save(user);

        log.info("Password reset: requestId={}, userId={}", requestId, userId);

        return ResetPasswordResponse.builder()
            .temporaryPassword(temporaryPassword)
            .build();
    }

    /**
     * 更新用户登录信息
     */
    @Transactional
    public void updateLoginInfo(String tenantId, String userId, String loginIp) {
        TenantUser user = tenantUserRepository.findByTenantIdAndUserId(tenantId, userId)
            .orElseThrow(() -> new BusinessException(ErrorCode.ERR_USER_NOT_FOUND));

        user.setLastLoginAt(Instant.now());
        user.setLastLoginIp(loginIp);
        user.setLoginCount(user.getLoginCount() + 1);
        user.setFailedLoginCount(0); // 登录成功，清空失败计数

        tenantUserRepository.save(user);
    }

    /**
     * 增加登录失败计数
     */
    @Transactional
    public void incrementFailedLoginCount(String tenantId, String userId) {
        tenantUserRepository.findByTenantIdAndUserId(tenantId, userId)
            .ifPresent(user -> {
                user.setFailedLoginCount(user.getFailedLoginCount() + 1);
                tenantUserRepository.save(user);
            });
    }

    /**
     * 获取角色列表
     */
    public List<RoleResponse> getRoles() {
        return ROLE_PERMISSIONS.entrySet().stream()
            .map(entry -> RoleResponse.builder()
                .name(entry.getKey())
                .description(ROLE_DESCRIPTIONS.getOrDefault(entry.getKey(), ""))
                .permissions(entry.getValue())
                .build())
            .toList();
    }

    /**
     * 获取权限列表
     */
    public List<PermissionResponse> getPermissions() {
        return PERMISSIONS.stream()
            .map(p -> PermissionResponse.builder()
                .name(p.name)
                .description(p.description)
                .category(p.category)
                .build())
            .toList();
    }

    // ========== 辅助方法 ==========

    private Sort buildSort(String sortBy, Boolean descending) {
        if (sortBy == null || sortBy.isBlank()) {
            sortBy = "createdAt";
        }
        Sort.Direction direction = Boolean.TRUE.equals(descending) ? Sort.Direction.DESC : Sort.Direction.ASC;
        return Sort.by(direction, sortBy);
    }

    private UserDetailResponse toUserDetailResponse(TenantUser user) {
        String[] roles = new String[]{user.getRole()};
        String[] permissions = getPermissionsForRole(user.getRole());

        return UserDetailResponse.builder()
            .id(user.getUserId())
            .username(user.getUsername())
            .email(user.getEmail())
            .roles(roles)
            .permissions(permissions)
            .status(user.getStatus())
            .lastLoginAt(user.getLastLoginAt())
            .createdAt(user.getCreatedAt())
            .lastLoginIp(user.getLastLoginIp())
            .loginCount(user.getLoginCount())
            .failedLoginCount(user.getFailedLoginCount())
            .updatedAt(user.getUpdatedAt())
            .build();
    }

    private String[] getPermissionsForRole(String role) {
        return ROLE_PERMISSIONS.getOrDefault(role, new String[0]);
    }

    private String generateUserId() {
        return "user_" + java.util.UUID.randomUUID().toString().substring(0, 8);
    }

    private String generateTemporaryPassword() {
        SecureRandom random = new SecureRandom();
        String chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%";
        StringBuilder sb = new StringBuilder(12);
        for (int i = 0; i < 12; i++) {
            sb.append(chars.charAt(random.nextInt(chars.length())));
        }
        return sb.toString();
    }

    private record PermissionInfo(String name, String description, String category) {}
}