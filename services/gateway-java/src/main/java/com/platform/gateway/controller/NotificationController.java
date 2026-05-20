package com.platform.gateway.controller;

import com.platform.gateway.dto.response.NotificationResponse;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.UnreadCountResponse;
import com.platform.gateway.service.NotificationService;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * 通知控制器
 *
 * <p>管理用户通知的查询、标记已读、删除等操作。
 *
 * <h3>API 端点列表</h3>
 * <pre>
 * ┌──────────────────────────────────────────────────────────────────────────────┐
 * │ 方法   │ 路径                                │ 描述                │ 权限要求   │
 * ├────────┼─────────────────────────────────────┼─────────────────────┼────────────┤
 * │ GET    │ /api/v1/notifications               │ 分页查询通知列表    │ 登录用户   │
 * │ GET    │ /api/v1/notifications/unread-count  │ 获取未读数量        │ 登录用户   │
 * │ PATCH  │ /api/v1/notifications/{id}/read     │ 标记单条已读        │ 登录用户   │
 * │ PATCH  │ /api/v1/notifications/read-all      │ 全部标记已读        │ 登录用户   │
 * │ DELETE │ /api/v1/notifications/{id}          │ 删除单条通知        │ 登录用户   │
 * │ DELETE │ /api/v1/notifications/read          │ 删除所有已读通知    │ 登录用户   │
 * └────────┴─────────────────────────────────────┴─────────────────────┴────────────┘
 * </pre>
 *
 * <h3>通知类型</h3>
 * <ul>
 *   <li>approval: 审批通知</li>
 *   <li>system: 系统通知</li>
 *   <li>alert: 告警通知</li>
 *   <li>info: 信息通知</li>
 *   <li>error: 错误通知</li>
 *   <li>success: 成功通知</li>
 * </ul>
 *
 * <h3>优先级</h3>
 * <ul>
 *   <li>low: 低优先级</li>
 *   <li>normal: 普通优先级（默认）</li>
 *   <li>high: 高优先级</li>
 *   <li>urgent: 紧急</li>
 * </ul>
 *
 * <h3>安全说明</h3>
 * <ul>
 *   <li>租户隔离：所有操作自动校验 tenantId</li>
 *   <li>用户绑定：只能操作自己的通知</li>
 *   <li>审计日志：关键操作记录审计日志</li>
 * </ul>
 *
 * <h3>日志规范</h3>
 * <ul>
 *   <li>INFO: 请求开始/结束，关键操作结果</li>
 *   <li>DEBUG: 详细参数（脱敏后）</li>
 *   <li>WARN: 业务异常</li>
 *   <li>ERROR: 系统异常</li>
 * </ul>
 *
 * @see NotificationService
 * @see com.platform.gateway.dto.response.NotificationResponse
 * @see com.platform.gateway.dto.response.UnreadCountResponse
 * @since 1.0.0
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/notifications")
@RequiredArgsConstructor
public class NotificationController {

    private final NotificationService notificationService;
    private final TenantContextService tenantContextService;

    /**
     * 分页查询通知列表
     *
     * <p>获取当前用户的通知列表，支持按类型和已读状态筛选。
     *
     * <h4>查询参数</h4>
     * <ul>
     *   <li><b>type</b>：通知类型（可选）- approval/system/alert/info/error/success</li>
     *   <li><b>read</b>：已读状态（可选）- true/false</li>
     *   <li><b>pageNumber</b>：页码（默认 1）</li>
     *   <li><b>pageSize</b>：每页大小（默认 20，最大 100）</li>
     * </ul>
     *
     * <h4>响应示例</h4>
     * <pre>{@code
     * {
     *   "items": [
     *     {
     *       "id": "550e8400-e29b-41d4-a716-446655440000",
     *       "type": "approval",
     *       "title": "待审批任务",
     *       "message": "您有一条新的审批任务需要处理",
     *       "read": false,
     *       "priority": "high",
     *       "actionUrl": "/approvals/xxx",
     *       "createdAt": "2026-06-06T10:00:00Z"
     *     }
     *   ],
     *   "totalCount": 15,
     *   "pageNumber": 1,
     *   "totalPages": 1,
     *   "hasNext": false
     * }
     * }</pre>
     *
     * @param type 通知类型（可选）
     * @param read 已读状态（可选）
     * @param pageNumber 页码（默认 1）
     * @param pageSize 每页大小（默认 20）
     * @return 分页的通知列表
     */
    @GetMapping
    public ResponseEntity<PageResponse<NotificationResponse>> getNotifications(
            @RequestParam(required = false) String type,
            @RequestParam(required = false) Boolean read,
            @RequestParam(defaultValue = "1") Integer pageNumber,
            @RequestParam(defaultValue = "20") Integer pageSize) {

        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Get notifications: requestId={}, tenant={}, user={}, type={}, read={}, page={}, size={}",
                requestId, tenantId, userId, type, read, pageNumber, pageSize);

        // 限制每页最大数量
        if (pageSize > 100) {
            pageSize = 100;
        }

        PageResponse<NotificationResponse> response = notificationService.listNotifications(
                tenantId, userId, type, read, pageNumber, pageSize);

        log.info("Get notifications result: requestId={}, total={}, page={}",
                requestId, response.getTotalCount(), response.getPageNumber());

        return ResponseEntity.ok(response);
    }

    /**
     * 获取未读通知数量
     *
     * <p>返回当前用户的未读通知总数，用于角标显示。
     *
     * <h4>响应示例</h4>
     * <pre>{@code
     * {
     *   "unreadCount": 5
     * }
     * }</pre>
     *
     * @return 未读数量响应
     */
    @GetMapping("/unread-count")
    public ResponseEntity<UnreadCountResponse> getUnreadCount() {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Get unread count: requestId={}, tenant={}, user={}",
                requestId, tenantId, userId);

        UnreadCountResponse response = notificationService.getUnreadCount(tenantId, userId);

        log.info("Get unread count result: requestId={}, count={}",
                requestId, response.getUnreadCount());

        return ResponseEntity.ok(response);
    }

    /**
     * 标记单条通知为已读
     *
     * <p>将指定的通知标记为已读状态。已读通知再次标记无副作用（幂等）。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>只能操作自己的通知</li>
     *   <li>通知不存在返回 404</li>
     *   <li>已读通知重复标记返回成功</li>
     * </ul>
     *
     * @param notificationId 通知 ID（UUID 格式）
     * @return 无内容响应
     */
    @PatchMapping("/{notificationId}/read")
    public ResponseEntity<Void> markAsRead(@PathVariable String notificationId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Mark notification as read: requestId={}, notificationId={}, tenant={}, user={}",
                requestId, notificationId, tenantId, userId);

        notificationService.markAsRead(notificationId, tenantId, userId);

        log.info("Notification marked as read: requestId={}, notificationId={}",
                requestId, notificationId);

        return ResponseEntity.noContent().build();
    }

    /**
     * 标记所有通知为已读
     *
     * <p>将当前用户的所有未读通知标记为已读。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>只影响未读通知</li>
     *   <li>已读通知不受影响</li>
     * </ul>
     *
     * @return 无内容响应
     */
    @PatchMapping("/read-all")
    public ResponseEntity<Void> markAllAsRead() {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Mark all notifications as read: requestId={}, tenant={}, user={}",
                requestId, tenantId, userId);

        int count = notificationService.markAllAsRead(tenantId, userId);

        log.info("All notifications marked as read: requestId={}, count={}", requestId, count);

        return ResponseEntity.noContent().build();
    }

    /**
     * 删除单条通知
     *
     * <p>删除指定的通知记录。删除后无法恢复。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>只能删除自己的通知</li>
     *   <li>通知不存在返回 404</li>
     * </ul>
     *
     * @param notificationId 通知 ID（UUID 格式）
     * @return 无内容响应
     */
    @DeleteMapping("/{notificationId}")
    public ResponseEntity<Void> deleteNotification(@PathVariable String notificationId) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Delete notification: requestId={}, notificationId={}, tenant={}, user={}",
                requestId, notificationId, tenantId, userId);

        notificationService.deleteNotification(notificationId, tenantId, userId);

        log.info("Notification deleted: requestId={}, notificationId={}", requestId, notificationId);

        return ResponseEntity.noContent().build();
    }

    /**
     * 删除所有已读通知
     *
     * <p>批量删除当前用户已阅读的通知记录。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>只删除已读状态的通知</li>
     *   <li>未读通知不受影响</li>
     * </ul>
     *
     * @return 无内容响应
     */
    @DeleteMapping("/read")
    public ResponseEntity<Void> deleteReadNotifications() {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Delete read notifications: requestId={}, tenant={}, user={}",
                requestId, tenantId, userId);

        int count = notificationService.deleteReadNotifications(tenantId, userId);

        log.info("Read notifications deleted: requestId={}, count={}", requestId, count);

        return ResponseEntity.noContent().build();
    }
}