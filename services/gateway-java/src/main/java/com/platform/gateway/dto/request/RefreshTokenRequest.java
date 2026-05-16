package com.platform.gateway.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 刷新 Token 请求 DTO
 *
 * <p>用于使用有效的 Refresh Token 获取新的 Access Token。
 * 当 Access Token 过期时，前端应调用此接口无感刷新。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/auth/refresh - 刷新令牌接口</li>
 *   <li>POST /api/v1/auth/logout - 登出接口（可选参数）</li>
 * </ul>
 *
 * <p>【Token 刷新策略】
 * <ul>
 *   <li>仅刷新 Access Token，Refresh Token 保持不变</li>
 *   <li>若 Refresh Token 即将过期（&lt; 1 天），同时返回新的 Refresh Token</li>
 *   <li>旧的 Refresh Token 立即失效</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.AuthController#refreshToken
 * @see com.platform.gateway.dto.response.RefreshTokenResponse
 */
@Data
public class RefreshTokenRequest {

    /**
     * Refresh Token
     *
     * <p>用于刷新 Access Token 的长期令牌。
     *
     * <p>【格式】JWT 格式的 Refresh Token
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项，不能为空</li>
     *   <li>必须是有效的 Refresh Token</li>
     *   <li>Token 未过期</li>
     *   <li>Token 未被撤销</li>
     * </ul>
     *
     * <p>【有效期】7 天
     */
    @NotBlank(message = "Refresh token不能为空")
    private String refreshToken;
}