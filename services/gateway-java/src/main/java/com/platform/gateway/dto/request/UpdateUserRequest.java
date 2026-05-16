package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 更新用户请求 DTO
 *
 * <p>用于部分更新用户信息（PATCH 语义）。仅更新请求中提供的字段。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>PATCH /api/v1/users/{id} - 更新用户信息接口</li>
 * </ul>
 *
 * <p>【权限要求】user:write
 *
 * <p>【限制】不能修改自己的角色（防止权限提升）
 *
 * @see com.platform.gateway.controller.UserController#updateUser
 * @see com.platform.gateway.dto.response.UserDetailResponse
 */
@Data
public class UpdateUserRequest {

    /**
     * 用户名
     *
     * <p>新的登录用户名。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>选填项</li>
     *   <li>长度 2-50 字符</li>
     *   <li>租户内唯一</li>
     * </ul>
     */
    @Size(min = 2, max = 50, message = "用户名长度需在2-50之间")
    private String username;

    /**
     * 邮箱地址
     *
     * <p>新的邮箱地址。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>选填项</li>
     *   <li>符合邮箱格式</li>
     *   <li>租户内唯一</li>
     * </ul>
     */
    @Email(message = "邮箱格式不正确")
    private String email;

    /**
     * 角色列表
     *
     * <p>更新用户的角色分配。若提供，将替换现有角色。
     *
     * <p>【格式】角色 ID 数组，如 ["admin", "user"]
     *
     * <p>【验证规则】
     * <ul>
     *   <li>选填项</li>
     *   <li>必须是系统中存在的有效角色</li>
     * </ul>
     *
     * <p>【限制】不能修改自己的角色
     */
    private String[] roles;

    /**
     * 用户状态
     *
     * <p>更新用户的账户状态。
     *
     * <p>【可选值】
     * <ul>
     *   <li>active - 活跃状态</li>
     *   <li>disabled - 禁用状态</li>
     *   <li>locked - 锁定状态</li>
     * </ul>
     */
    private String status;
}
