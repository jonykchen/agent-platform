package com.platform.gateway.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * 通知实体
 *
 * <p>用于存储系统通知、审批通知、告警通知等用户通知信息。
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
 * <h3>设计说明</h3>
 * <ul>
 *   <li>租户隔离：所有通知按 tenant_id 隔离</li>
 *   <li>用户绑定：通知与具体用户关联，支持用户级通知管理</li>
 *   <li>已读标记：支持单个和批量已读标记</li>
 *   <li>关联链接：可选的 actionUrl 用于跳转到相关页面</li>
 * </ul>
 *
 * @see com.platform.gateway.repository.NotificationRepository
 * @see com.platform.gateway.service.NotificationService
 * @since 1.0.0
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "notifications", indexes = {
    @Index(name = "idx_notification_tenant_user", columnList = "tenant_id, user_id"),
    @Index(name = "idx_notification_user_read", columnList = "user_id, read"),
    @Index(name = "idx_notification_created", columnList = "created_at DESC")
})
public class Notification {

    /**
     * 通知 ID（主键）
     */
    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id", updatable = false, nullable = false)
    private UUID id;

    /**
     * 租户 ID
     *
     * <p>用于多租户数据隔离。
     */
    @Column(name = "tenant_id", nullable = false, length = 64)
    private String tenantId;

    /**
     * 用户 ID
     *
     * <p>通知所属用户的唯一标识。
     */
    @Column(name = "user_id", nullable = false, length = 128)
    private String userId;

    /**
     * 通知类型
     *
     * <p>可选值：approval、system、alert、info、error、success
     */
    @Column(name = "type", nullable = false, length = 32)
    private String type;

    /**
     * 通知标题
     *
     * <p>通知的简短标题，用于列表展示。
     */
    @Column(name = "title", nullable = false)
    private String title;

    /**
     * 通知内容
     *
     * <p>通知的详细内容。
     */
    @Column(name = "message", columnDefinition = "TEXT")
    private String message;

    /**
     * 已读标记
     *
     * <p>标记通知是否已被用户阅读。
     */
    @Column(name = "read", nullable = false)
    @Builder.Default
    private Boolean read = false;

    /**
     * 优先级
     *
     * <p>可选值：low、normal、high、urgent
     */
    @Column(name = "priority", length = 16)
    @Builder.Default
    private String priority = "normal";

    /**
     * 关联链接
     *
     * <p>点击通知后跳转的 URL。
     */
    @Column(name = "action_url", length = 512)
    private String actionUrl;

    /**
     * 创建时间
     *
     * <p>通知的创建时间，不可修改。
     */
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    /**
     * 实体持久化前的回调
     *
     * <p>自动设置创建时间和默认值。
     */
    @PrePersist
    protected void onCreate() {
        this.createdAt = Instant.now();
        if (this.read == null) {
            this.read = false;
        }
        if (this.priority == null) {
            this.priority = "normal";
        }
    }
}