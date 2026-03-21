package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 刷新Token响应
 */
@Data
@Builder
public class RefreshTokenResponse {

    private TokenInfo tokens;

    @Data
    @Builder
    public static class TokenInfo {
        private String accessToken;
        private String refreshToken;
        private Integer expiresIn;
        private String tokenType;
    }
}