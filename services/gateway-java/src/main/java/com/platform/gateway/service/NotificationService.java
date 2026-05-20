package com.platform.gateway.service;

import com.platform.gateway.dto.response.NotificationResponse;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.UnreadCountResponse;
import com.platform.gateway.entity.Notification;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.NotificationRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

/**
 * 通知服务
 *
 * <p>负责用户通知的管理，包括查询、标记已读、删除等操作。
 *
 * <h3>核心功能</h3>
 * <ul>
 *   <li>通知列表查询：支持分页、按类型/已读状态筛选</li>
 *   <li>未读计数：获取用户未读通知数量</li>
 *   <li>标记已读：单条或批量标记</li>
 *   <li>删除通知：单条删除或批量清理已读通知</li>
 * </ul>
 *
 * <h3>通知类型</h3>
 * <ul>
 *   <li>approval: 审批通知 - 审批任务相关（如待审批提醒、审批结果）</li>
 *   <li>system: 系统通知 - 系统运维、配置变更、版本更新</li>
 *   <li>alert: 告警通知 - 异常告警、阈值预警、服务状态变化</li>
 *   <li>info: 信息通知 - 一般信息提醒</li>
 *   <li>error: 错误通知 - 错误、异常情况</li>
 *   <li>success: 成功通知 - 操作成功、任务完成</li>
 * </ul>
 *
 * <h3>依赖关系</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          服务依赖关系                                        │
 * │                                                                             │
 * │   NotificationController                                                    │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   NotificationService                                                       │
 * │       │                                                                     │
 * │       └──► NotificationRepository (数据持久化)                              │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>事务处理</h3>
 * <p>写操作（标记已读、删除）使用 {@code @Transactional} 保证数据一致性。
 *
 * @see Notification 通知实体
 * @see NotificationRepository 通知仓库
 * @see com.platform.gateway.controller.NotificationController
 * @since 1.0.0
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final NotificationRepository notificationRepository;

    /**
     * 分页查询用户通知列表
     *
     * <p>支持按类型和已读状态筛选，结果按创建时间倒序排列。
     *
     * <h4>查询条件</h4>
     * <ul>
     *   <li><b>type</b>：通知类型（可选）</li>
     *   <li><b>read</b>：已读状态（可选）</li>
     * </ul>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能查询本租户的通知</li>
     *   <li>用户绑定：只能查询自己的通知</li>
     *   <li>默认排序：按创建时间降序</li>
     * </ul>
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @param type 通知类型（可选）
     * @param read 已读状态（可选）
     * @param pageNumber 页码（从 1 开始）
     * @param pageSize 每页大小
     * @return 分页的通知响应
     */
    public PageResponse<NotificationResponse> listNotifications(
            String tenantId,
            String userId,
            String type,
            Boolean read,
            Integer pageNumber,
            Integer pageSize) {

        // 构建分页参数
        int page = pageNumber != null && pageNumber > 0 ? pageNumber - 1 : 0;
        int size = pageSize != null && pageSize > 0 ? pageSize : 20;
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "createdAt"));

        // 查询
        Page<Notification> notificationPage;
        if (read != null) {
            notificationPage = notificationRepository.findByTenantIdAndUserIdAndReadOrderByCreatedAtDesc(
                    tenantId, userId, read, pageable);
        } else {
            notificationPage = notificationRepository.findByTenantIdAndUserIdOrderByCreatedAtDesc(
                    tenantId, userId, pageable);
        }

        // 按类型筛选（内存过滤，因为类型筛选通常不是主要查询条件）
        List<NotificationResponse> items;
        if (type != null && !type.isEmpty()) {
            items = notificationPage.getContent().stream()
                    .filter(n -> type.equals(n.getType()))
                    .map(this::toResponse)
                    .toList();
        } else {
            items = notificationPage.getContent().stream()
                    .map(this::toResponse)
                    .toList();
        }

        return PageResponse.<NotificationResponse>builder()
                .items(items)
                .totalCount(notificationPage.getTotalElements())
                .pageNumber(pageNumber != null ? pageNumber : 1)
                .totalPages(notificationPage.getTotalPages())
                .hasNext(notificationPage.hasNext())
                .build();
    }

    /**
     * 获取未读通知数量
     *
     * <p>返回当前用户的未读通知总数，用于角标显示。
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @return 未读数量响应
     */
    public UnreadCountResponse getUnreadCount(String tenantId, String userId) {
        long count = notificationRepository.countByTenantIdAndUserIdAndRead(tenantId, userId, false);
        return UnreadCountResponse.builder()
                .unreadCount(count)
                .build();
    }

    /**
     * 标记单条通知为已读
     *
     * <p>将指定 ID 的通知标记为已读状态。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能操作本租户的通知</li>
     *   <li>用户绑定：只能操作自己的通知</li>
     *   <li>幂等性：已读通知重复标记无副作用</li>
     * </ul>
     *
     * @param notificationId 通知 ID（UUID 格式）
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @throws BusinessException ERR_NOT_FOUND 通知不存在
     * @throws BusinessException ERR_FORBIDDEN 无权访问
     */
    @Transactional
    public void markAsRead(String notificationId, String tenantId, String userId) {
        UUID id = parseUUID(notificationId);

        Notification notification = notificationRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_NOT_FOUND, "通知不存在"));

        // 租户和用户校验
        if (!notification.getTenantId().equals(tenantId)) {
            throw new BusinessException(ErrorCode.ERR_FORBIDDEN, "无权访问该通知");
        }
        if (!notification.getUserId().equals(userId)) {
            throw new BusinessException(ErrorCode.ERR_FORBIDDEN, "无权访问该通知");
        }

        // 标记已读（幂等）
        if (!notification.getRead()) {
            notification.setRead(true);
            notificationRepository.save(notification);
            log.info("Notification marked as read: id={}, userId={}", notificationId, userId);
        }
    }

    /**
     * 批量标记所有通知为已读
     *
     * <p>将用户的所有未读通知标记为已读。
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @return 更新的记录数
     */
    @Transactional
    public int markAllAsRead(String tenantId, String userId) {
        int count = notificationRepository.markAllAsRead(tenantId, userId);
        log.info("All notifications marked as read: userId={}, count={}", userId, count);
        return count;
    }

    /**
     * 删除单条通知
     *
     * <p>删除指定 ID 的通知记录。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能删除本租户的通知</li>
     *   <li>用户绑定：只能删除自己的通知</li>
     * </ul>
     *
     * @param notificationId 通知 ID（UUID 格式）
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @throws BusinessException ERR_NOT_FOUND 通知不存在
     * @throws BusinessException ERR_FORBIDDEN 无权访问
     */
    @Transactional
    public void deleteNotification(String notificationId, String tenantId, String userId) {
        UUID id = parseUUID(notificationId);

        Notification notification = notificationRepository.findById(id)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_NOT_FOUND, "通知不存在"));

        // 租户和用户校验
        if (!notification.getTenantId().equals(tenantId)) {
            throw new BusinessException(ErrorCode.ERR_FORBIDDEN, "无权访问该通知");
        }
        if (!notification.getUserId().equals(userId)) {
            throw new BusinessException(ErrorCode.ERR_FORBIDDEN, "无权访问该通知");
        }

        notificationRepository.delete(notification);
        log.info("Notification deleted: id={}, userId={}", notificationId, userId);
    }

    /**
     * 删除所有已读通知
     *
     * <p>批量清理用户已阅读的通知记录，释放存储空间。
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @return 删除的记录数
     */
    @Transactional
    public int deleteReadNotifications(String tenantId, String userId) {
        int count = notificationRepository.deleteReadNotifications(tenantId, userId);
        log.info("Read notifications deleted: userId={}, count={}", userId, count);
        return count;
    }

    /**
     * 创建通知（内部方法）
     *
     * <p>由其他服务调用，创建新的通知。
     * 例如审批服务可以调用此方法创建审批通知。
     *
     * @param notification 通知实体
     * @return 创建后的通知响应
     */
    @Transactional
    public NotificationResponse createNotification(Notification notification) {
        notification = notificationRepository.save(notification);
        log.info("Notification created: id={}, userId={}, type={}",
                notification.getId(), notification.getUserId(), notification.getType());
        return toResponse(notification);
    }

    // ========== 辅助方法 ==========

    private NotificationResponse toResponse(Notification notification) {
        return NotificationResponse.builder()
                .id(notification.getId().toString())
                .type(notification.getType())
                .title(notification.getTitle())
                .message(notification.getMessage())
                .read(notification.getRead())
                .priority(notification.getPriority())
                .actionUrl(notification.getActionUrl())
                .createdAt(notification.getCreatedAt())
                .build();
    }

    private UUID parseUUID(String str) {
        try {
            return UUID.fromString(str);
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.ERR_INVALID_REQUEST, "ID 格式错误");
        }
    }
}