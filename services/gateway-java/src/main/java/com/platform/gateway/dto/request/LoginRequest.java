package com.platform.gateway.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 登录请求 DTO
 *
 * <p>用于用户身份认证，验证成功后返回 Access Token 和 Refresh Token。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/auth/login - 用户登录接口</li>
 * </ul>
 *
 * <p>【安全措施】
 * <ul>
 *   <li>登录失败不区分"用户不存在"和"密码错误"</li>
 *   <li>连续失败触发账户锁定</li>
 *   <li>密码在日志中脱敏</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.AuthController#login
 * @see com.platform.gateway.dto.response.LoginResponse
 */
@Data
public class LoginRequest {

    /**
     * 用户名
     *
     * <p>用户的登录用户名。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项，不能为空</li>
     * </ul>
     */
    @NotBlank(message = "用户名不能为空")
    private String username;

    /**
     * 密码
     *
     * <p>用户的登录密码。传输时应使用 HTTPS 加密。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项，不能为空</li>
     * </ul>
     *
     * <p>【安全提示】密码不在日志中记录明文
     */
    @NotBlank(message = "密码不能为空")
    private String password;

    /**
     * 租户ID
     *
     * <p>多租户场景下指定登录的租户。若不填写，系统会根据用户所属租户自动匹配。
     *
     * <p>【格式】UUID 格式，如 "tenant_001"
     * <p>【验证规则】选填项
     */
    private String tenantId;
}