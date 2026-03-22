package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 更新用户请求
 */
@Data
public class UpdateUserRequest {

    @Size(min = 2, max = 50, message = "用户名长度需在2-50之间")
    private String username;

    @Email(message = "邮箱格式不正确")
    private String email;

    /** 角色 */
    private String[] roles;

    /** 状态 */
    private String status;
}
