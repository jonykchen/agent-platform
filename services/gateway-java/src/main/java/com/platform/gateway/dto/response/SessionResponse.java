package com.platform.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.UUID;

/**
 * 会话响应 DTO
 *
 * <p>会话的基本信息响应，用于会话列表展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/sessions - 获取会话列表</li>
 *   <li>POST /api/v1/sessions - 创建会话</li>
 *   <li>GET /api/v1/sessions/{id} - 获取会话详情</li>
 * </ul>
 *
 * <p>【会话状态】
 * <ul>
 *   <li>active: 活跃状态，可继续对话</li>
 *   <li>archived: 已归档，只读状态</li>
 *   <li>closed: 已关闭，不可操作</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.SessionController
 * @see com.platform.gateway.dto.request.CreateSessionRequest
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class SessionResponse {

    /**
     * 会话ID
     *
     * <p>会话的唯一标识。
     *
     * <p>【格式】UUID 格式
     */
    private UUID id;

    /**
     * 租户ID
     *
     * <p>会话所属租户。
     *
     * <p>【格式】UUID 格式
     */
    private String tenantId;

    /**
     * 用户ID
     *
     * <p>会话所属用户。
     *
     * <p>【格式】UUID 格式
     */
    private String userId;

    /**
     * 会话类型
     *
     * <p>会话的交互类型。
     *
     * <p>【可选值】chat、task、workflow
     */
    private String sessionType;

    /**
     * 会话标题
     *
     * <p>会话的显示标题，用于列表展示。
     */
    private String title;

    /**
     * 会话状态
     *
     * <p>会话的当前状态。
     *
     * <p>【可选值】active、archived、closed
     */
    private String status;

    /**
     * 创建时间
     *
     * <p>会话的创建时间（ISO 8601 格式）。
     */
    private Instant createdAt;

    /**
     * 更新时间
     *
     * <p>会话最后更新时间，如最后一条消息时间（ISO 8601 格式）。
     */
    private Instant updatedAt;

    /**
     * 消息数量
     *
     * <p>该会话的 AgentRun 数量。
     *
     * <p>【前端字段】messages_count
     */
    private Integer messagesCount;

    /**
     * 最后一条消息摘要
     *
     * <p>最后一个 Run 的 outputMessage 摘要（截取前100字符）。
     *
     * <p>【前端字段】last_message
     */
    private String lastMessage;

    /**
     * 最后消息时间
     *
     * <p>最后一个 Run 的 completedAt 或 createdAt。
     *
     * <p>【前端字段】last_message_at
     */
    private Instant lastMessageAt;
}