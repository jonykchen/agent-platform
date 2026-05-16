package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 权限响应 DTO
 *
 * <p>权限信息响应，包含权限名称、描述和类别。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/permissions - 获取权限列表</li>
 * </ul>
 *
 * <p>【权限要求】permission:read
 *
 * @see com.platform.gateway.controller.PermissionController
 */
@Data
@Builder
public class PermissionResponse {

    /**
     * 权限名称
     *
     * <p>权限的唯一标识名称，采用 resource:action 格式。
     *
     * <p>【示例】user:read、user:write、approval:approve
     */
    private String name;

    /**
     * 权限描述
     *
     * <p>权限的功能描述和用途说明。
     */
    private String description;

    /**
     * 权限类别
     *
     * <p>权限所属的功能类别。
     *
     * <p>【示例】user、role、approval、system
     */
    private String category;
}