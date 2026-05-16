package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 活跃告警响应 DTO
 *
 * <p>当前活跃的系统告警信息，用于仪表盘告警展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/dashboard/alerts - 获取活跃告警列表</li>
 * </ul>
 *
 * <p>【告警类型】
 * <ul>
 *   <li>error: 错误级别，需要立即处理</li>
 *   <li>warning: 警告级别，需要关注</li>
 *   <li>info: 信息级别，仅供参考</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.DashboardController
 */
@Data
@Builder
public class ActiveAlertResponse {

    /**
     * 告警ID
     *
     * <p>告警的唯一标识。
     *
     * <p>【格式】UUID 格式
     */
    private String id;

    /**
     * 告警类型
     *
     * <p>告警的严重级别。
     *
     * <p>【可选值】error（错误）、warning（警告）、info（信息）
     */
    private String type;

    /**
     * 告警消息
     *
     * <p>告警的详细描述信息。
     */
    private String message;

    /**
     * 来源
     *
     * <p>产生告警的来源服务或组件。
     *
     * <p>【示例】gateway、orchestrator、model-gateway
     */
    private String source;

    /**
     * 创建时间
     *
     * <p>告警产生的时间。
     *
     * <p>【格式】ISO 8601 格式，如 "2026-05-01T10:30:00Z"
     */
    private String createdAt;
}
