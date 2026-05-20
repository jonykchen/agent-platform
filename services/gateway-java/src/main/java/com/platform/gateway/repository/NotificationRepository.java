package com.platform.gateway.repository;

import com.platform.gateway.entity.Notification;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.UUID;

/**
 * 通知 Repository
 *
 * <p>提供通知数据的持久化操作接口。
 *
 * <h3>核心查询方法</h3>
 * <ul>
 *   <li>{@link #findByTenantIdAndUserIdOrderByCreatedAtDesc} - 分页查询用户通知列表</li>
 *   <li>{@link #findByTenantIdAndUserIdAndReadOrderByCreatedAtDesc} - 按已读状态筛选</li>
 *   <li>{@link #countByTenantIdAndUserIdAndRead} - 统计未读数量</li>
 *   <li>{@link #markAllAsRead} - 批量标记已读</li>
 *   <li>{@link #deleteReadNotifications} - 删除已读通知</li>
 * </ul>
 *
 * <h3>租户隔离</h3>
 * <p>所有查询都包含 tenantId 参数，确保数据隔离。
 *
 * @see Notification
 * @see com.platform.gateway.service.NotificationService
 * @since 1.0.0
 */
@Repository
public interface NotificationRepository extends JpaRepository<Notification, UUID> {

    /**
     * 分页查询用户通知列表
     *
     * <p>按创建时间倒序返回用户的所有通知。
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @param pageable 分页参数
     * @return 通知分页结果
     */
    Page<Notification> findByTenantIdAndUserIdOrderByCreatedAtDesc(
            String tenantId,
            String userId,
            Pageable pageable);

    /**
     * 分页查询用户通知列表（按已读状态筛选）
     *
     * <p>按已读状态筛选并按创建时间倒序返回。
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @param read 已读状态
     * @param pageable 分页参数
     * @return 通知分页结果
     */
    Page<Notification> findByTenantIdAndUserIdAndReadOrderByCreatedAtDesc(
            String tenantId,
            String userId,
            Boolean read,
            Pageable pageable);

    /**
     * 统计用户未读通知数量
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @param read 已读状态
     * @return 符合条件的通知数量
     */
    long countByTenantIdAndUserIdAndRead(String tenantId, String userId, Boolean read);

    /**
     * 批量标记用户所有通知为已读
     *
     * <p>将指定用户的所有未读通知标记为已读。
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @return 更新的记录数
     */
    @Modifying
    @Query("UPDATE Notification n SET n.read = true WHERE n.tenantId = :tenantId AND n.userId = :userId AND n.read = false")
    int markAllAsRead(@Param("tenantId") String tenantId, @Param("userId") String userId);

    /**
     * 删除用户已读通知
     *
     * <p>清理用户已阅读的通知记录。
     *
     * @param tenantId 租户 ID
     * @param userId 用户 ID
     * @return 删除的记录数
     */
    @Modifying
    @Query("DELETE FROM Notification n WHERE n.tenantId = :tenantId AND n.userId = :userId AND n.read = true")
    int deleteReadNotifications(@Param("tenantId") String tenantId, @Param("userId") String userId);
}