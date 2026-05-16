package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 分页响应包装 DTO
 *
 * <p>另一种分页响应结构，采用 snake_case 字段命名风格。
 * 用于部分接口的分页响应。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/approvals - 审批列表</li>
 *   <li>GET /api/v1/audit/events - 审计事件列表</li>
 * </ul>
 *
 * <p>【字段命名】采用 snake_case 风格，如 page_size、total_pages
 *
 * @param <T> 数据项类型
 * @see com.platform.gateway.controller.ApprovalController
 * @see com.platform.gateway.controller.AuditController
 */
@Data
@Builder
public class PagedResponse<T> {

    /**
     * 数据列表
     *
     * <p>当前页的数据列表。
     */
    private List<T> items;

    /**
     * 总数量
     *
     * <p>符合查询条件的总记录数。
     */
    private Long total;

    /**
     * 当前页码
     *
     * <p>当前页码，从 1 开始。
     */
    private Integer page;

    /**
     * 每页大小
     *
     * <p>每页返回的记录数。
     */
    private Integer page_size;

    /**
     * 总页数
     *
     * <p>总页数，根据 total 和 page_size 计算得出。
     */
    private Integer total_pages;
}
