package com.platform.gateway.dto.request;

import lombok.Data;

import java.time.Instant;

/**
 * 审计事件查询请求 DTO
 *
 * <p>用于查询审计日志，支持按事件类型、时间范围、用户等多维度筛选。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/audit/events - 查询审计事件列表</li>
 * </ul>
 *
 * <p>【权限要求】audit:read
 *
 * <p>【审计说明】
 * <ul>
 *   <li>审计日志不可删除或修改（符合 G-SEC-03）</li>
 *   <li>查询操作本身会被记录</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.AuditController
 * @see com.platform.gateway.dto.response.AuditEventResponse
 */
@Data
public class AuditQueryRequest {

    /**
     * 页码
     *
     * <p>分页查询的页码，从 1 开始。
     *
     * <p>【默认值】1
     */
    private Integer pageNumber = 1;

    /**
     * 每页大小
     *
     * <p>每页返回的记录数。
     *
     * <p>【默认值】20
     */
    private Integer pageSize = 20;

    /**
     * 事件类型
     *
     * <p>按事件类型筛选，如 LOGIN、logout、CREATE_USER 等。
     *
     * <p>【选填】不填则返回所有类型
     */
    private String eventType;

    /**
     * 事件分类
     *
     * <p>按事件分类筛选，如 AUTH、USER、SYSTEM 等。
     *
     * <p>【选填】不填则返回所有分类
     */
    private String eventCategory;

    /**
     * 严重级别
     *
     * <p>按严重级别筛选。
     *
     * <p>【可选值】info、warning、error、critical
     */
    private String severity;

    /**
     * 用户ID
     *
     * <p>按操作用户筛选。
     *
     * <p>【格式】UUID 格式
     */
    private String userId;

    /**
     * 资源类型
     *
     * <p>按资源类型筛选，如 user、session、approval 等。
     */
    private String resourceType;

    /**
     * 资源ID
     *
     * <p>按具体资源 ID 筛选。
     *
     * <p>【格式】UUID 格式
     */
    private String resourceId;

    /**
     * 开始时间
     *
     * <p>查询时间范围的起始时间（ISO 8601 格式）。
     */
    private Instant startTime;

    /**
     * 结束时间
     *
     * <p>查询时间范围的结束时间（ISO 8601 格式）。
     */
    private Instant endTime;

    /**
     * 排序字段
     *
     * <p>指定排序的字段。
     *
     * <p>【可选值】createdAt、updatedAt、severity 等
     */
    private String sortBy;

    /**
     * 是否降序
     *
     * <p>是否按降序排列。
     *
     * <p>【默认值】true（最新记录在前）
     */
    private Boolean sortDescending = true;
}
