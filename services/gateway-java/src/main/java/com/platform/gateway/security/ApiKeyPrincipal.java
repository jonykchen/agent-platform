package com.platform.gateway.security;

import lombok.Getter;
import org.springframework.security.core.GrantedAuthority;

import java.util.List;

/**
 * API Key 身份主体
 *
 * 用于服务间调用或外部系统集成的身份信息
 */
@Getter
public class ApiKeyPrincipal {

    private final String type;      // svc/ext/test
    private final String userId;
    private final String tenantId;
    private final List<GrantedAuthority> authorities;

    public ApiKeyPrincipal(String type, String userId, String tenantId, List<GrantedAuthority> authorities) {
        this.type = type;
        this.userId = userId;
        this.tenantId = tenantId;
        this.authorities = authorities;
    }
}