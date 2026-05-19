package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.Map;

/**
 * 审批任务响应 DTO
 *
 * <p>审批任务的完整信息，用于审批列表展示和审批操作。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>GET /api/v1/approvals - 获取审批任务列表</li>
 *   <li>GET /api/v1/approvals/{id} - 获取审批任务详情</li>
 * </ul>
 *
 * <p>【审批状态】
 * <ul>
 *   <li>pending: 待审批</li>
 *   <li>approved: 已批准</li>
 *   <li>rejected: 已拒绝</li>
 *   <li>expired: 已过期</li>
 * </ul>
 *
 * <p>【优先级】
 * <ul>
 *   <li>low: 低优先级</li>
 *   <li>medium: 中优先级</li>
 *   <li>high: 高优先级</li>
 *   <li>critical: 紧急</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.ApprovalController
 * @see com.platform.gateway.dto.request.ApprovalListRequest
 * @see com.platform.gateway.dto.request.ApprovalActionRequest
 */
@Data
@Builder
public class ApprovalTaskResponse {

    /**
     * 审批任务 ID
     *
     * <p>审批任务的唯一标识。
     *
     * <p>【格式】UUID 格式
     */
    private String id;

    /**
     * 运行实例 ID
     *
     * <p>触发审批的 Agent 运行实例标识。
     *
     * <p>【格式】run_xxx
     */
    private String runId;

    /**
     * 工具调用 ID
     *
     * <p>触发审批的工具调用标识。
     *
     * <p>【格式】call_xxx
     */
    private String toolInvocationId;

    /**
     * 租户 ID
     *
     * <p>审批任务所属租户。
     *
     * <p>【格式】UUID 格式
     */
    private String tenantId;

    /**
     * 任务类型
     *
     * <p>审批任务的类型分类。
     *
     * <p>【示例】payment、data_access、config_change
     */
    private String taskType;

    /**
     * 任务标题
     *
     * <p>审批任务的简短标题，用于列表展示。
     */
    private String title;

    /**
     * 任务描述
     *
     * <p>审批任务的详细描述，说明审批的具体内容。
     */
    private String description;

    /**
     * 请求上下文
     *
     * <p>触发审批的工具参数等上下文信息（JSON 格式）。
     *
     * <p>【用途】审批人查看请求详情
     */
    private Map<String, Object> requestContext;

    /**
     * 请求者 ID
     *
     * <p>发起审批请求的用户 ID。
     *
     * <p>【格式】UUID 格式
     */
    private String requesterId;

    /**
     * 指派审批人 ID
     *
     * <p>被指派处理该审批的用户 ID。
     *
     * <p>【格式】UUID 格式
     */
    private String assigneeId;

    /**
     * 优先级
     *
     * <p>审批任务的优先级。
     *
     * <p>【可选值】low、medium、high、critical
     */
    private String priority;

    /**
     * 状态
     *
     * <p>审批任务的当前状态。
     *
     * <p>【可选值】pending、approved、rejected、expired
     */
    private String status;

    /**
     * 审批人 ID
     *
     * <p>实际审批操作的用户 ID（审批完成后设置）。
     *
     * <p>【格式】UUID 格式
     */
    private String reviewerId;

    /**
     * 审批意见
     *
     * <p>审批人提交的审批意见或备注。
     */
    private String reviewComment;

    /**
     * 审批时间
     *
     * <p>审批操作的时间（ISO 8601 格式）。
     */
    private Instant reviewedAt;

    /**
     * 过期时间
     *
     * <p>审批任务的过期时间，超期未审批将自动过期。
     *
     * <p>【格式】ISO 8601 格式
     */
    private Instant expiresAt;

    /**
     * 创建时间
     *
     * <p>审批任务的创建时间（ISO 8601 格式）。
     */
    private Instant createdAt;

    /**
     * 更新时间
     *
     * <p>审批任务最后更新时间（ISO 8601 格式）。
     */
    private Instant updatedAt;
}
