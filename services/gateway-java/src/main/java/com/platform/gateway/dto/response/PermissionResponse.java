package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 权限响应
 */
@Data
@Builder
public class PermissionResponse {

    /** 权限名称 */
    private String name;

    /** 权限描述 */
    private String description;

    /** 权限类别 */
    private String category;
}