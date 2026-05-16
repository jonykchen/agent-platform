package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 刷新 Token 响应 DTO
 *
 * <p>使用 Refresh Token 获取新的 Access Token 后返回的响应。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/auth/refresh - 刷新令牌接口</li>
 * </ul>
 *
 * <p>【刷新策略】
 * <ul>
 *   <li>仅刷新 Access Token，Refresh Token 保持不变</li>
 *   <li>若 Refresh Token 即将过期（&lt; 1 天），同时返回新的 Refresh Token</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.AuthController#refreshToken
 * @see com.platform.gateway.dto.request.RefreshTokenRequest
 */
@Data
@Builder
public class RefreshTokenResponse {

    /**
     * 用户ID
     *
     * <p>从 Refresh Token 解析出的用户 ID。
     *
     * <p>【格式】UUID 格式
     */
    private String userId;

    /**
     * 令牌信息
     *
     * <p>新的访问令牌和刷新令牌。
     */
    private TokenInfo tokens;

    /**
     * 令牌信息
     *
     * <p>认证所需的访问令牌和刷新令牌。
     */
    @Data
    @Builder
    public static class TokenInfo {

        /**
         * Access Token
         *
         * <p>新的访问令牌，用于 API 访问。
         *
         * <p>【有效期】15 分钟
         * <p>【格式】JWT 格式
         */
        private String accessToken;

        /**
         * Refresh Token
         *
         * <p>刷新令牌。通常与原 Refresh Token 相同，
         * 仅当即将过期时才会返回新的 Refresh Token。
         *
         * <p>【有效期】7 天
         * <p>【格式】JWT 格式
         */
        private String refreshToken;

        /**
         * 过期时间（秒）
         *
         * <p>Access Token 的有效期（秒）。
         */
        private Integer expiresIn;

        /**
         * 令牌类型
         *
         * <p>固定值 "Bearer"。
         */
        private String tokenType;
    }
}