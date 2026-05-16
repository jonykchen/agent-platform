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
 *
 * <p>负责租户内用户的 CRUD 操作、角色权限管理和安全策略。
 * 是 Gateway 用户管理的核心服务。
 *
 * <h3>核心概念：多租户用户隔离</h3>
 *
 * <p>每个用户属于一个租户，不同租户的用户完全隔离：
 * <ul>
 *   <li><b>数据隔离</b>：查询和操作都带 tenantId 条件</li>
 *   <li><b>用户名隔离</b>：用户名在租户内唯一，不同租户可同名</li>
 *   <li><b>权限隔离</b>：用户只能管理本租户的用户</li>
 * </ul>
 *
 * <h3>依赖关系</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          服务依赖关系                                        │
 * │                                                                             │
 * │   UserController                                                            │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   UserService ◄────────────────────────────────────────────────────────────│
 * │       │                                                                     │
 * │       ├──► TenantUserRepository (用户数据持久化)                            │
 * │       │                                                                     │
 * │       ├──► PasswordEncoder (密码加密)                                        │
 * │       │                                                                     │
 * │       └──► AuthService (登录信息更新回调)                                    │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>技术选型：事务处理</h3>
 * <ul>
 *   <li><b>读操作</b>：无事务，支持脏读优化</li>
 *   <li><b>写操作</b>：{@code @Transactional}，保证原子性</li>
 *   <li><b>乐观锁</b>：通过 updatedAt 字段防止并发冲突</li>
 * </ul>
 *
 * <h3>角色权限模型</h3>
 *
 * <p>采用 RBAC（Role-Based Access Control）模型：
 * <pre>
 *   ┌──────────┬───────────────────────────────────────────────────────────────┐
 *   │ Role     │ Description                    │ Permissions                  │
 *   ├──────────┼────────────────────────────────┼──────────────────────────────┤
 *   │ admin    │ 系统管理员，拥有全部权限         │ *                            │
 *   │ operator │ 操作员，可执行工具和审批         │ chat:*, approval:*, tools:*  │
 *   │ viewer   │ 观察者，只读权限                 │ chat:read, approval:read     │
 *   └──────────┴────────────────────────────────┴──────────────────────────────┘
 * </pre>
 *
 * <h3>设计模式：工厂方法</h3>
 *
 * <p>{@link #createUser} 和 {@link #generateUserId} 采用工厂方法模式，
 * 封装用户实体的创建逻辑和 ID 生成策略。
 *
 * <h3>安全策略</h3>
 * <ul>
 *   <li><b>密码存储</b>：BCrypt 单向加密，不可逆</li>
 *   <li><b>临时密码</b>：重置密码生成 12 位随机字符串</li>
 *   <li><b>登录失败</b>：记录失败次数，支持锁定策略</li>
 * </ul>
 *
 * @see TenantUser 用户实体
 * @see TenantUserRepository 用户仓库
 * @since 1.0.0
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
     * 获取用户列表（分页）
     *
     * <p>查询租户内所有用户，支持条件筛选和排序。
     *
     * <h4>查询条件</h4>
     * <ul>
     *   <li><b>status</b>：用户状态（active/inactive）</li>
     *   <li><b>role</b>：角色（admin/operator/viewer）</li>
     * </ul>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能查询本租户用户</li>
     *   <li>权限控制：需要 user:read 权限</li>
     *   <li>默认排序：按创建时间降序</li>
     * </ul>
     *
     * @param tenantId 租户ID，用于租户隔离
     * @param params 查询参数，包含分页、排序和筛选条件
     * @return 分页的用户详情响应
     * @since 1.0.0
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
     *
     * <p>查询指定用户的完整信息，包括角色和权限列表。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能查询本租户用户</li>
     *   <li>权限控制：需要 user:read 权限</li>
     * </ul>
     *
     * @param tenantId 租户ID，用于租户隔离
     * @param userId 用户ID（格式：user_xxxxxxxx）
     * @return 用户详情响应
     * @throws BusinessException ERR_USER_NOT_FOUND 用户不存在
     * @since 1.0.0
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
     *
     * <p>在租户内创建新用户，自动生成用户ID并加密密码。
     *
     * <h4>处理流程</h4>
     * <ol>
     *   <li>检查用户名唯一性（租户内）</li>
     *   <li>生成用户ID（格式：user_xxxxxxxx）</li>
     *   <li>加密密码（BCrypt）</li>
     *   <li>设置默认配额和初始状态</li>
     *   <li>持久化用户实体</li>
     * </ol>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>用户名在租户内必须唯一</li>
     *   <li>默认状态为 active</li>
     *   <li>默认日配额为 100000 tokens</li>
     *   <li>主角色取 roles 数组第一个元素</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param request 创建用户请求，包含用户名、密码、邮箱、角色
     * @return 创建后的用户详情
     * @throws BusinessException ERR_USER_ALREADY_EXISTS 用户名已存在
     * @since 1.0.0
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
     *
     * <p>更新用户的基本信息和角色。支持部分更新。
     *
     * <h4>可更新字段</h4>
     * <ul>
     *   <li><b>username</b>：用户名（需检查唯一性）</li>
     *   <li><b>email</b>：邮箱</li>
     *   <li><b>roles</b>：角色（主角色取第一个元素）</li>
     *   <li><b>status</b>：状态</li>
     * </ul>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>更新用户名需检查唯一性</li>
     *   <li>租户隔离：只能更新本租户用户</li>
     *   <li>权限控制：需要 user:write 权限</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param userId 用户ID
     * @param request 更新用户请求
     * @return 更新后的用户详情
     * @throws BusinessException ERR_USER_NOT_FOUND 用户不存在
     * @throws BusinessException ERR_USER_ALREADY_EXISTS 用户名已存在
     * @since 1.0.0
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
     *
     * <p>将用户状态设置为 inactive，禁止用户登录和使用系统。
     * 已登录用户的 Access Token 在过期前仍有效。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>状态变为 inactive</li>
     *   <li>租户隔离：只能禁用本租户用户</li>
     *   <li>权限控制：需要 user:write 权限</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param userId 用户ID
     * @throws BusinessException ERR_USER_NOT_FOUND 用户不存在
     * @since 1.0.0
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
     *
     * <p>将用户状态设置为 active，允许用户登录和使用系统。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>状态变为 active</li>
     *   <li>租户隔离：只能启用本租户用户</li>
     *   <li>权限控制：需要 user:write 权限</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param userId 用户ID
     * @throws BusinessException ERR_USER_NOT_FOUND 用户不存在
     * @since 1.0.0
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
     *
     * <p>生成临时密码并重置用户密码。临时密码需要用户尽快修改。
     *
     * <h4>处理流程</h4>
     * <ol>
     *   <li>查找用户</li>
     *   <li>生成 12 位随机临时密码（包含大小写字母、数字和特殊字符）</li>
     *   <li>加密并存储新密码</li>
     *   <li>返回临时密码（明文，仅此一次）</li>
     * </ol>
     *
     * <h4>安全措施</h4>
     * <ul>
     *   <li><b>随机性</b>：使用 {@link SecureRandom} 生成密码</li>
     *   <li><b>复杂度</b>：12 位，包含大小写、数字、特殊字符</li>
     *   <li><b>审计日志</b>：记录密码重置事件</li>
     * </ul>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能重置本租户用户密码</li>
     *   <li>权限控制：需要 user:write 权限</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param userId 用户ID
     * @return 重置密码响应，包含临时密码
     * @throws BusinessException ERR_USER_NOT_FOUND 用户不存在
     * @since 1.0.0
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
     * 更新用户登录信息（内部方法）
     *
     * <p>登录成功后更新用户的登录统计信息。
     * 由 {@link AuthService#login} 调用。
     *
     * <h4>更新内容</h4>
     * <ul>
     *   <li>lastLoginAt：最后登录时间</li>
     *   <li>lastLoginIp：最后登录IP</li>
     *   <li>loginCount：登录次数 +1</li>
     *   <li>failedLoginCount：失败计数清零</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param userId 用户ID
     * @param loginIp 登录IP地址
     * @since 1.0.0
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
     * 增加登录失败计数（内部方法）
     *
     * <p>登录失败后增加失败计数。
     * 由 {@link AuthService#login} 调用。
     *
     * <h4>安全策略</h4>
     * <ul>
     *   <li>记录失败次数用于暴力破解检测</li>
     *   <li>达到阈值可触发账户锁定（MVP 未实现）</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param userId 用户ID
     * @since 1.0.0
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
     *
     * <p>返回系统支持的所有角色及其权限配置。
     * 用于前端角色选择器展示。
     *
     * <h4>预定义角色</h4>
     * <ul>
     *   <li><b>admin</b>：系统管理员，拥有全部权限</li>
     *   <li><b>operator</b>：操作员，可执行工具和审批</li>
     *   <li><b>viewer</b>：观察者，只读权限</li>
     * </ul>
     *
     * @return 角色响应列表
     * @since 1.0.0
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
     *
     * <p>返回系统支持的所有权限及其分类。
     * 用于前端权限展示和配置。
     *
     * <h4>权限分类</h4>
     * <ul>
     *   <li><b>chat</b>：对话相关（chat:read, chat:write）</li>
     *   <li><b>approval</b>：审批相关（approval:read, approval:approve）</li>
     *   <li><b>tools</b>：工具执行（tools:execute）</li>
     *   <li><b>user</b>：用户管理（user:read, user:write）</li>
     *   <li><b>tenant</b>：租户管理（tenant:read, tenant:write）</li>
     *   <li><b>system</b>：系统权限（* = 全部权限）</li>
     * </ul>
     *
     * @return 权限响应列表
     * @since 1.0.0
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