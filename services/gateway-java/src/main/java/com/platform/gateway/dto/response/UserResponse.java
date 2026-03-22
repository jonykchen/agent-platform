package com.platform.gateway.dto.response;

import lombok.Data;
import lombok.experimental.SuperBuilder;

import java.time.Instant;

/**
 * 用户响应
 */
@Data
@SuperBuilder
public class UserResponse {

    /** 用户ID */
    private String id;

    /** 用户名 */
    private String username;

    /** 邮箱 */
    private String email;

    /** 角色列表 */
    private String[] roles;

    /** 权限列表 */
    private String[] permissions;

    /** 状态 */
    private String status;

    /** 最后登录时间 */
    private Instant lastLoginAt;

    /** 创建时间 */
    private Instant createdAt;
}
