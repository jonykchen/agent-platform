package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 用户查询参数
 */
@Data
public class UserQueryParams {

    /** 用户名（模糊搜索） */
    private String username;

    /** 邮箱（模糊搜索） */
    private String email;

    /** 状态筛选 */
    private String status;

    /** 角色筛选 */
    private String role;

    /** 页码，从1开始 */
    @Min(value = 1, message = "页码最小为1")
    private Integer pageNumber = 1;

    /** 每页数量 */
    @Min(value = 1, message = "每页数量最小为1")
    @Max(value = 100, message = "每页数量最大为100")
    private Integer pageSize = 20;

    /** 排序字段 */
    private String sortBy;

    /** 是否降序 */
    private Boolean sortDescending = false;
}
