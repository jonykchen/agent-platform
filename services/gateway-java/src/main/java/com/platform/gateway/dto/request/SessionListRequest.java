package com.platform.gateway.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Data;

/**
 * 会话列表查询请求 DTO
 *
 * <p>用于查询当前用户的会话列表。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/sessions - 获取会话列表</li>
 * </ul>
 *
 * <p>【数据范围】只返回当前用户所属租户的会话
 *
 * <p>【筛选条件】支持按状态筛选和标题搜索
 *
 * @see com.platform.gateway.controller.SessionController
 * @see com.platform.gateway.dto.response.PagedResponse
 * @see com.platform.gateway.dto.response.SessionResponse
 */
@Data
public class SessionListRequest {

    /**
     * 会话状态过滤
     *
     * <p>按会话状态筛选。
     *
     * <p>【可选值】
     * <ul>
     *   <li>active - 活跃状态</li>
     *   <li>archived - 已归档</li>
     *   <li>closed - 已关闭</li>
     * </ul>
     */
    private String status;

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
     * 每页大小
     *
     * <p>每页返回的记录数。
     *
     * <p>【默认值】20
     * <p>【取值范围】1 ~ 100
     */
    @Min(value = 1, message = "每页大小最小为1")
    @Max(value = 100, message = "每页大小最大为100")
    private Integer pageSize = 20;

    /**
     * 标题搜索关键词
     *
     * <p>按会话标题模糊搜索。
     *
     * <p>【选填】支持模糊匹配
     */
    private String search;
}
