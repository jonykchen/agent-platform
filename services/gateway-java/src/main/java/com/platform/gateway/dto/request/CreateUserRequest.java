package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 创建用户请求 DTO
 *
 * <p>用于在租户下创建新用户。系统会自动生成临时密码并发送给用户。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/users - 创建用户接口</li>
 * </ul>
 *
 * <p>【权限要求】user:write
 *
 * <p>【数据校验】
 * <ul>
 *   <li>用户名：必填，2-50 字符，租户内唯一</li>
 *   <li>邮箱：必填，符合邮箱格式，租户内唯一</li>
 *   <li>密码：必填，8-128 字符</li>
 *   <li>角色：必填，必须是有效角色 ID</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.UserController#createUser
 * @see com.platform.gateway.dto.response.UserDetailResponse
 */
@Data
public class CreateUserRequest {

    /**
     * 用户名
     *
     * <p>用户的登录用户名，用于身份认证。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项</li>
     *   <li>长度 2-50 字符</li>
     *   <li>租户内唯一</li>
     * </ul>
     */
    @NotBlank(message = "用户名不能为空")
    @Size(min = 2, max = 50, message = "用户名长度需在2-50之间")
    private String username;

    /**
     * 邮箱地址
     *
     * <p>用户的邮箱地址，用于接收系统通知和密码重置。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项</li>
     *   <li>符合邮箱格式</li>
     *   <li>租户内唯一</li>
     * </ul>
     */
    @NotBlank(message = "邮箱不能为空")
    @Email(message = "邮箱格式不正确")
    private String email;

    /**
     * 初始密码
     *
     * <p>用户的初始登录密码。系统会要求用户首次登录时修改密码。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项</li>
     *   <li>长度 8-128 字符</li>
     *   <li>建议包含大小写字母、数字和特殊字符</li>
     * </ul>
     *
     * <p>【安全提示】密码不在日志中记录明文
     */
    @NotBlank(message = "密码不能为空")
    @Size(min = 8, max = 128, message = "密码长度需在8-128之间")
    private String password;

    /**
     * 角色列表
     *
     * <p>分配给用户的角色 ID 数组。角色决定了用户的权限范围。
     *
     * <p>【格式】角色 ID 数组，如 ["admin", "user"]
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项，不能为空数组</li>
     *   <li>必须是系统中存在的有效角色</li>
     * </ul>
     */
    @NotEmpty(message = "角色不能为空")
    private String[] roles;
}