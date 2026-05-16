package com.platform.gateway.dto.response;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.experimental.SuperBuilder;

import java.time.Instant;

/**
 * 用户详情响应 DTO
 *
 * <p>用户完整信息响应，包含更多安全和统计信息，用于用户详情展示。
 * 继承 {@link UserResponse}，增加登录统计和安全相关字段。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/users/{id} - 获取用户详情</li>
 *   <li>POST /api/v1/users - 创建用户后的响应</li>
 *   <li>PATCH /api/v1/users/{id} - 更新用户后的响应</li>
 * </ul>
 *
 * <p>【权限要求】user:read
 *
 * @see com.platform.gateway.controller.UserController#getUser
 * @see com.platform.gateway.controller.UserController#createUser
 * @see UserResponse
 */
@Data
@SuperBuilder
@EqualsAndHashCode(callSuper = true)
public class UserDetailResponse extends UserResponse {

    /**
     * 最后登录IP
     *
     * <p>用户最后一次成功登录的 IP 地址。
     *
     * <p>【格式】IPv4 或 IPv6 地址
     */
    private String lastLoginIp;

    /**
     * 登录次数
     *
     * <p>用户累计成功登录的次数。
     */
    private Integer loginCount;

    /**
     * 登录失败次数
     *
     * <p>连续登录失败的次数，达到阈值后账户会被锁定。
     *
     * <p>【安全说明】成功登录后重置为 0
     */
    private Integer failedLoginCount;

    /**
     * 更新时间
     *
     * <p>用户信息最后一次更新的时间。
     */
    private Instant updatedAt;
}
