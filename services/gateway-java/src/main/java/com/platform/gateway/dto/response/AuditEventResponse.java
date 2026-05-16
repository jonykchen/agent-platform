package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.Map;

/**
 * 审计事件响应 DTO
 *
 * <p>审计事件的完整信息，用于审计日志查询和展示。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/audit/events - 查询审计事件列表</li>
 *   <li>GET /api/v1/audit/events/{id} - 查询审计事件详情</li>
 * </ul>
 *
 * <p>【审计说明】
 * <ul>
 *   <li>审计日志不可删除或修改（符合 G-SEC-03）</li>
 *   <li>记录所有关键操作（登录、用户管理、审批等）</li>
 * </ul>
 *
 * <p>【字段说明】
 * <ul>
 *   <li>beforeState/afterState: 数据变更前后状态</li>
 *   <li>details: 附加的审计详情</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.AuditController
 * @see com.platform.gateway.dto.request.AuditQueryRequest
 */
@Data
@Builder
public class AuditEventResponse {

    /**
     * 事件ID（数据库自增）
     *
     * <p>数据库自增主键。
     */
    private Long id;

    /**
     * 事件唯一标识
     *
     * <p>事件的 UUID 标识，用于唯一标识一个审计事件。
     *
     * <p>【格式】UUID 格式
     */
    private String eventId;

    /**
     * 事件类型
     *
     * <p>事件的具体类型，如 LOGIN、LOGOUT、CREATE_USER、UPDATE_USER 等。
     */
    private String eventType;

    /**
     * 事件分类
     *
     * <p>事件的分类，如 AUTH、USER、SYSTEM、DATA 等。
     */
    private String eventCategory;

    /**
     * 严重级别
     *
     * <p>事件的严重级别。
     *
     * <p>【可选值】info、warning、error、critical
     */
    private String severity;

    /**
     * 租户ID
     *
     * <p>发生事件的租户标识。
     *
     * <p>【格式】UUID 格式
     */
    private String tenantId;

    /**
     * 用户ID
     *
     * <p>触发事件的用户标识。
     *
     * <p>【格式】UUID 格式
     */
    private String userId;

    /**
     * 资源类型
     *
     * <p>被操作资源的类型，如 user、session、approval、config 等。
     */
    private String resourceType;

    /**
     * 资源ID
     *
     * <p>被操作资源的具体标识。
     *
     * <p>【格式】UUID 格式
     */
    private String resourceId;

    /**
     * 操作动作
     *
     * <p>对资源执行的动作，如 create、update、delete、read、execute 等。
     */
    private String action;

    /**
     * 变更前状态
     *
     * <p>数据变更前的状态快照（JSON 格式）。
     * 对于创建操作为 null，对于更新操作包含变更前的数据。
     */
    private Map<String, Object> beforeState;

    /**
     * 变更后状态
     *
     * <p>数据变更后的状态快照（JSON 格式）。
     * 对于删除操作为 null，对于创建/更新操作包含变更后的数据。
     */
    private Map<String, Object> afterState;

    /**
     * 事件详情
     *
     * <p>附加的审计详情（JSON 格式），如登录 IP、客户端信息等。
     */
    private Map<String, Object> details;

    /**
     * 请求ID
     *
     * <p>触发事件的请求追踪标识。
     *
     * <p>【格式】req_xxx
     */
    private String requestId;

    /**
     * 分布式追踪ID
     *
     * <p>用于分布式链路追踪的标识。
     *
     * <p>【格式】由 OpenTelemetry 生成
     */
    private String traceId;

    /**
     * IP 地址
     *
     * <p>触发事件的客户端 IP 地址。
     */
    private String ipAddress;

    /**
     * User-Agent
     *
     * <p>客户端的 User-Agent 信息。
     */
    private String userAgent;

    /**
     * 来源服务
     *
     * <p>产生事件的服务名称，如 gateway、orchestrator 等。
     */
    private String sourceService;

    /**
     * 创建时间
     *
     * <p>事件发生的准确时间（ISO 8601 格式）。
     */
    private Instant createdAt;
}
