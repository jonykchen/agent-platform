package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;

/**
 * 通知响应 DTO
 *
 * <p>通知信息的响应结构，用于通知列表和详情展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/notifications - 获取通知列表</li>
 *   <li>GET /api/v1/notifications/{id} - 获取通知详情</li>
 * </ul>
 *
 * <p>【通知类型】
 * <ul>
 *   <li>approval: 审批通知 - 审批任务相关通知</li>
 *   <li>system: 系统通知 - 系统运维、配置变更等</li>
 *   <li>alert: 告警通知 - 异常告警、阈值预警</li>
 *   <li>info: 信息通知 - 一般信息提醒</li>
 *   <li>error: 错误通知 - 错误、异常情况通知</li>
 *   <li>success: 成功通知 - 操作成功、任务完成通知</li>
 * </ul>
 *
 * <p>【优先级】
 * <ul>
 *   <li>low: 低优先级 - 不紧急的信息</li>
 *   <li>normal: 普通优先级 - 默认级别</li>
 *   <li>high: 高优先级 - 需要及时关注</li>
 *   <li>urgent: 紧急 - 需要立即处理</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.NotificationController
 * @see com.platform.gateway.service.NotificationService
 * @since 1.0.0
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class NotificationResponse {

    /**
     * 通知 ID
     *
     * <p>通知的唯一标识（UUID 格式）。
     */
    private String id;

    /**
     * 通知类型
     *
     * <p>可选值：approval、system、alert、info、error、success
     */
    private String type;

    /**
     * 通知标题
     *
     * <p>通知的简短标题，用于列表展示。
     */
    private String title;

    /**
     * 通知内容
     *
     * <p>通知的详细描述内容。
     */
    private String message;

    /**
     * 已读状态
     *
     * <p>标记通知是否已被用户阅读。
     */
    private Boolean read;

    /**
     * 优先级
     *
     * <p>可选值：low、normal、high、urgent
     */
    private String priority;

    /**
     * 关联链接
     *
     * <p>点击通知后跳转的 URL，可选。
     */
    private String actionUrl;

    /**
     * 创建时间
     *
     * <p>通知的创建时间（ISO 8601 格式）。
     */
    private Instant createdAt;
}