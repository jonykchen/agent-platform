package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 重置密码响应 DTO
 *
 * <p>管理员重置用户密码后返回的响应，包含临时密码。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/users/{id}/reset-password - 重置用户密码</li>
 * </ul>
 *
 * <p>【权限要求】user:write
 *
 * <p>【安全说明】
 * <ul>
 *   <li>临时密码 24 小时内有效</li>
 *   <li>首次登录强制修改密码</li>
 *   <li>重置后所有现有 Token 立即失效</li>
 *   <li>临时密码不在日志中记录</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.UserController#resetPassword
 */
@Data
@Builder
public class ResetPasswordResponse {

    /**
     * 临时密码
     *
     * <p>系统生成的临时密码，用户需使用此密码登录并修改。
     *
     * <p>【有效期】24 小时
     *
     * <p>【安全提示】
     * <ul>
     *   <li>临时密码仅显示一次，请妥善保管</li>
     *   <li>用户首次登录时必须修改密码</li>
     *   <li>临时密码不在日志中记录</li>
     * </ul>
     */
    private String temporaryPassword;
}