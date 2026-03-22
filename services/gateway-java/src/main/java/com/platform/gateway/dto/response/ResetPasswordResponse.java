package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 重置密码响应
 */
@Data
@Builder
public class ResetPasswordResponse {

    /** 临时密码 */
    private String temporaryPassword;
}