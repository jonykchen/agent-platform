package com.platform.gateway.dto.response;

import lombok.Data;
import lombok.experimental.SuperBuilder;

import java.time.Instant;

/**
 * 用户响应 DTO
 *
 * <p>用户基本信息响应，用于用户列表展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/users - 分页查询用户列表</li>
 * </ul>
 *
 * <p>【权限要求】user:read
 *
 * @see com.platform.gateway.controller.UserController#getUsers
 * @see UserDetailResponse
 */
@Data
@SuperBuilder
public class UserResponse {

    /**
     * 用户ID
     *
     * <p>用户的唯一标识。
     *
     * <p>【格式】UUID 格式
     */
    private String id;

    /**
     * 用户名
     *
     * <p>用户的登录用户名。
     */
    private String username;

    /**
     * 邮箱地址
     *
     * <p>用户的邮箱地址。
     */
    private String email;

    /**
     * 角色列表
     *
     * <p>用户拥有的角色列表。
     */
    private String[] roles;

    /**
     * 权限列表
     *
     * <p>用户拥有的权限列表，由角色派生。
     */
    private String[] permissions;

    /**
     * 状态
     *
     * <p>用户的账户状态。
     *
     * <p>【可选值】active（活跃）、disabled（禁用）、locked（锁定）
     */
    private String status;

    /**
     * 最后登录时间
     *
     * <p>用户最后一次成功登录的时间。
     */
    private Instant lastLoginAt;

    /**
     * 创建时间
     *
     * <p>用户账号的创建时间。
     */
    private Instant createdAt;
}
