package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 未读通知数量响应 DTO
 *
 * <p>返回用户未读通知的数量统计。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/notifications/unread-count - 获取未读数量</li>
 * </ul>
 *
 * <p>【使用场景】
 * <ul>
 *   <li>导航栏未读消息角标</li>
 *   <li>通知中心未读计数</li>
 *   <li>轮询检查新通知</li>
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
public class UnreadCountResponse {

    /**
     * 未读通知数量
     *
     * <p>当前用户未阅读的通知总数。
     */
    private Long unreadCount;
}