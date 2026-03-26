package com.platform.gateway.security;

import lombok.Getter;
import org.springframework.security.core.GrantedAuthority;

import java.util.List;

/**
 * 用户身份主体
 *
 * 存储在 Security Context 中的用户信息：
 * - userId: 用户唯一标识
 * - username: 用户名
 * - tenantId: 租户 ID（用于多租户隔离）
 */
@Getter
public class UserPrincipal {

    private final String userId;
    private final String username;
    private final String tenantId;

    public UserPrincipal(String userId, String username, String tenantId) {
        this.userId = userId;
        this.username = username;
        this.tenantId = tenantId;
    }
}