package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 角色响应 DTO
 *
 * <p>角色信息响应，包含角色名称、描述和权限列表。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/roles - 获取角色列表</li>
 *   <li>GET /api/v1/roles/{name} - 获取角色详情</li>
 * </ul>
 *
 * <p>【权限要求】role:read
 *
 * @see com.platform.gateway.controller.RoleController
 */
@Data
@Builder
public class RoleResponse {

    /**
     * 角色名称
     *
     * <p>角色的唯一标识名称。
     *
     * <p>【示例】admin、user、approver
     */
    private String name;

    /**
     * 角色描述
     *
     * <p>角色的功能描述和用途说明。
     */
    private String description;

    /**
     * 角色权限
     *
     * <p>角色拥有的权限列表。
     *
     * <p>【格式】权限字符串数组，如 ["user:read", "user:write"]
     */
    private String[] permissions;
}
