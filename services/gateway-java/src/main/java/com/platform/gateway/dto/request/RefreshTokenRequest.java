package com.platform.gateway.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * 刷新Token请求
 */
@Data
public class RefreshTokenRequest {

    @NotBlank(message = "Refresh token不能为空")
    private String refreshToken;
}