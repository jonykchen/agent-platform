package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.Map;

/**
 * 审计统计响应 DTO
 *
 * <p>审计事件的统计数据，用于仪表盘展示和监控。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/audit/stats - 获取审计统计</li>
 * </ul>
 *
 * <p>【统计维度】
 * <ul>
 *   <li>totalEvents: 事件总数</li>
 *   <li>bySeverity: 按严重级别分组统计</li>
 *   <li>byCategory: 按事件分类分组统计</li>
 *   <li>byEventType: 按事件类型分组统计</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.AuditController
 */
@Data
@Builder
public class AuditStatsResponse {

    /**
     * 事件总数
     *
     * <p>指定时间范围内的审计事件总数。
     */
    private Long totalEvents;

    /**
     * 按严重级别统计
     *
     * <p>按严重级别分组的事件数量。
     *
     * <p>【示例】{"info": 1000, "warning": 50, "error": 10, "critical": 2}
     */
    private Map<String, Long> bySeverity;

    /**
     * 按事件分类统计
     *
     * <p>按事件分类分组的事件数量。
     *
     * <p>【示例】{"AUTH": 500, "USER": 300, "SYSTEM": 262}
     */
    private Map<String, Long> byCategory;

    /**
     * 按事件类型统计
     *
     * <p>按事件类型分组的事件数量。
     *
     * <p>【示例】{"LOGIN": 300, "LOGOUT": 200, "CREATE_USER": 50}
     */
    private Map<String, Long> byEventType;
}
