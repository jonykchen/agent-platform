package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 登录响应 DTO
 *
 * <p>登录成功后返回的完整响应，包含用户信息、租户信息和令牌信息。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/auth/login - 用户登录接口</li>
 * </ul>
 *
 * <p>【响应结构】
 * <ul>
 *   <li>user: 登录用户的基本信息</li>
 *   <li>tenant: 用户所属租户信息</li>
 *   <li>tokens: 认证令牌信息</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.AuthController#login
 * @see com.platform.gateway.dto.request.LoginRequest
 */
@Data
@Builder
public class LoginResponse {

    /**
     * 用户信息
     */
    private UserInfo user;

    /**
     * 租户信息
     */
    private TenantInfo tenant;

    /**
     * 令牌信息
     */
    private TokenInfo tokens;

    /**
     * 用户信息
     *
     * <p>登录用户的基本信息。
     */
    @Data
    @Builder
    public static class UserInfo {

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
         * <p>登录用户名。
         */
        private String username;

        /**
         * 邮箱地址
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
    }

    /**
     * 租户信息
     *
     * <p>用户所属租户的基本信息。
     */
    @Data
    @Builder
    public static class TenantInfo {

        /**
         * 租户ID
         *
         * <p>租户的唯一标识。
         */
        private String id;

        /**
         * 租户名称
         */
        private String name;

        /**
         * 租户层级
         *
         * <p>租户的服务层级。
         *
         * <p>【可选值】free、standard、premium、enterprise
         */
        private String tier;

        /**
         * 可用特性列表
         *
         * <p>租户可使用的特性/功能列表。
         */
        private String[] features;
    }

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
         * <p>用于 API 访问的访问令牌。
         *
         * <p>【有效期】15 分钟
         * <p>【格式】JWT 格式
         */
        private String accessToken;

        /**
         * Refresh Token
         *
         * <p>用于刷新 Access Token 的刷新令牌。
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