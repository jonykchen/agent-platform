package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 用户查询参数 DTO
 *
 * <p>用于管理后台查询用户列表，支持多条件筛选和排序。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/users - 获取用户列表</li>
 * </ul>
 *
 * <p>【权限要求】user:read
 *
 * <p>【数据范围】只返回当前租户的用户
 *
 * @see com.platform.gateway.controller.UserController#getUsers
 * @see com.platform.gateway.dto.response.PageResponse
 * @see com.platform.gateway.dto.response.UserDetailResponse
 */
@Data
public class UserQueryParams {

    /**
     * 用户名（模糊搜索）
     *
     * <p>按用户名模糊匹配。
     *
     * <p>【选填】支持模糊匹配
     */
    private String username;

    /**
     * 邮箱（模糊搜索）
     *
     * <p>按邮箱地址模糊匹配。
     *
     * <p>【选填】支持模糊匹配
     */
    private String email;

    /**
     * 状态筛选
     *
     * <p>按用户状态筛选。
     *
     * <p>【可选值】active、disabled、locked
     */
    private String status;

    /**
     * 角色筛选
     *
     * <p>按用户角色筛选。
     *
     * <p>【示例】admin、user
     */
    private String role;

    /**
     * 页码
     *
     * <p>分页查询的页码，从 1 开始。
     *
     * <p>【默认值】1
     */
    @Min(value = 1, message = "页码最小为1")
    private Integer pageNumber = 1;

    /**
     * 每页数量
     *
     * <p>每页返回的记录数。
     *
     * <p>【默认值】20
     * <p>【取值范围】1 ~ 100
     */
    @Min(value = 1, message = "每页数量最小为1")
    @Max(value = 100, message = "每页数量最大为100")
    private Integer pageSize = 20;

    /**
     * 排序字段
     *
     * <p>指定排序的字段。
     *
     * <p>【可选值】createdAt、updatedAt、username、lastLoginAt
     */
    private String sortBy;

    /**
     * 是否降序
     *
     * <p>是否按降序排列。
     *
     * <p>【默认值】false（升序）
     */
    private Boolean sortDescending = false;
}
