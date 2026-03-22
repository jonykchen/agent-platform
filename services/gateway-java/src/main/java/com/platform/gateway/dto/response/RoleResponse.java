package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 角色响应
 */
@Data
@Builder
public class RoleResponse {

    /** 角色名称 */
    private String name;

    /** 角色描述 */
    private String description;

    /** 角色权限 */
    private String[] permissions;
}
