package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 登录响应
 */
@Data
@Builder
public class LoginResponse {

    private UserInfo user;
    private TenantInfo tenant;
    private TokenInfo tokens;

    @Data
    @Builder
    public static class UserInfo {
        private String id;
        private String username;
        private String email;
        private String[] roles;
        private String[] permissions;
    }

    @Data
    @Builder
    public static class TenantInfo {
        private String id;
        private String name;
        private String tier;
        private String[] features;
    }

    @Data
    @Builder
    public static class TokenInfo {
        private String accessToken;
        private String refreshToken;
        private Integer expiresIn;
        private String tokenType;
    }
}