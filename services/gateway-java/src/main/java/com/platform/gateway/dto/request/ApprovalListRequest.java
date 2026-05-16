package com.platform.gateway.dto.request;

import lombok.Data;

/**
 * 审批列表请求 DTO
 *
 * <p>用于查询待审批或已审批的任务列表。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/approvals - 获取审批列表</li>
 * </ul>
 *
 * <p>【权限要求】approval:read
 *
 * <p>【筛选条件】支持按状态、优先级、任务类型筛选
 *
 * @see com.platform.gateway.controller.ApprovalController
 * @see com.platform.gateway.dto.response.PagedResponse
 * @see com.platform.gateway.dto.response.ApprovalTaskResponse
 */
@Data
public class ApprovalListRequest {

    /**
     * 页码
     *
     * <p>分页查询的页码，从 1 开始。
     *
     * <p>【默认值】1
     */
    private Integer page = 1;

    /**
     * 每页大小
     *
     * <p>每页返回的记录数。
     *
     * <p>【默认值】10
     */
    private Integer page_size = 10;

    /**
     * 审批状态过滤
     *
     * <p>按审批状态筛选。
     *
     * <p>【可选值】pending、approved、rejected、expired
     */
    private String status;

    /**
     * 优先级过滤
     *
     * <p>按优先级筛选。
     *
     * <p>【可选值】low、medium、high、critical
     */
    private String priority;

    /**
     * 任务类型过滤
     *
     * <p>按任务类型筛选。
     *
     * <p>【示例】payment、data_access、config_change
     */
    private String task_type;

    /**
     * 排序字段
     *
     * <p>指定排序的字段。
     *
     * <p>【默认值】created_at
     * <p>【可选值】created_at、updated_at、priority
     */
    private String sort_by = "created_at";

    /**
     * 排序方向
     *
     * <p>排序的方向。
     *
     * <p>【默认值】desc（降序）
     * <p>【可选值】asc、desc
     */
    private String sort_order = "desc";
}
