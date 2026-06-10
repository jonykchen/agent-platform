package com.platform.gateway.controller;

import com.platform.gateway.audit.AuditLog;
import com.platform.gateway.dto.request.ApprovalActionRequest;
import com.platform.gateway.dto.request.ApprovalListRequest;
import com.platform.gateway.dto.response.ApprovalTaskResponse;
import com.platform.gateway.dto.response.PagedResponse;
import com.platform.gateway.service.ApprovalService;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

/**
 * 审批控制器
 *
 * 【核心职责】
 * 1. 管理审批任务的生命周期（查询、审批、拒绝）
 * 2. 提供审批任务的分页查询能力
 * 3. 确保审批操作的租户隔离和审计追踪
 *
 * 【API 端点列表】
 * ┌──────────────────────────────────────────────────────────────────────────────┐
 * │ 方法   │ 路径                        │ 描述                │ 权限要求       │
 * ├────────┼─────────────────────────────┼─────────────────────┼────────────────┤
 * │ GET    │ /api/v1/approvals           │ 分页查询审批列表    │ approval:read  │
 * │ GET    │ /api/v1/approvals/{id}      │ 获取审批详情        │ approval:read  │
 * │ POST   │ /api/v1/approvals/{id}/approve │ 通过审批         │ approval:write │
 * │ POST   │ /api/v1/approvals/{id}/reject  │ 拒绝审批         │ approval:write │
 * └────────┴─────────────────────────────┴─────────────────────┴────────────────┘
 *
 * 【技术选型】REST vs gRPC
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ REST (当前选择)    │ • 前端直接调用              │ • 无双向流式通信            │
 * │                    │ • 调试方便                  │ • 高并发性能略低于 gRPC     │
 * │                    │ • 符合 S-JAVA-01            │                              │
 * │                    │ • 无需 Protocol Buffers     │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ gRPC               │ • 高性能二进制协议          │ • 需要 Protocol Buffers     │
 * │                    │ • 双向流式通信              │ • 浏览器需 gRPC-Web 代理    │
 * │                    │ • 强类型契约                │ • 调试困难                  │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【技术选型】Spring MVC vs WebFlux
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Spring MVC (选择)  │ • 团队熟悉度高              │ • 线程阻塞模型              │
 * │                    │ • 生态成熟，调试方便        │ • 高并发需更多线程资源      │
 * │                    │ • 符合 S-JAVA-01            │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ WebFlux            │ • 非阻塞，高并发性能        │ • 学习曲线陡峭              │
 * │                    │ • 背压支持                   │ • 调试困难                  │
 * │                    │ • 更少线程资源              │ • 需要全链路响应式改造       │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【安全说明】
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * 权限要求：
 * - approval:read  - 查询审批任务
 * - approval:write - 执行审批操作（通过/拒绝）
 *
 * 租户隔离：
 * - 所有操作自动注入 tenantId，确保数据隔离
 * - 通过 TenantContextService 获取当前租户上下文
 *
 * 审计记录：
 * - 查询操作：记录查询条件（状态、分页参数）
 * - 审批操作：记录审批人、审批结果、审批时间
 * - 审计日志通过 ApprovalService 内部记录
 *
 * 【日志规范】
 * - INFO: 请求开始/结束，审批决策结果
 * - DEBUG: 详细参数（脱敏后）
 * - WARN: 业务异常（权限不足、数据不存在）
 * - ERROR: 系统异常
 *
 * @see ApprovalService
 * @see ApprovalTaskResponse
 * @see TenantContextService
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/approvals")
@RequiredArgsConstructor
public class ApprovalController {

    private final ApprovalService approvalService;
    private final TenantContextService tenantContextService;

    /**
     * 分页查询审批任务列表
     *
     * 【功能说明】
     * 根据查询条件分页获取审批任务列表，支持按状态、类型筛选。
     * 结果自动按租户隔离，只返回当前租户的审批任务。
     *
     * 【权限要求】
     * - approval:read
     *
     * 【审计标记】
     * - 操作类型：QUERY
     * - 审计字段：tenantId, userId, status, page, pageSize
     *
     * @param request 查询参数，包含状态、分页信息等
     * @return 分页的审批任务列表
     */
    @GetMapping
    @PreAuthorize("hasRole('admin') or hasAuthority('approval:read')")
    public ResponseEntity<PagedResponse<ApprovalTaskResponse>> listApprovals(ApprovalListRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("List approvals: requestId={}, tenant={}, user={}, status={}, page={}, pageSize={}",
                requestId, tenantId, userId, request.getStatus(), request.getPage(), request.getPage_size());

        PagedResponse<ApprovalTaskResponse> response = approvalService.listApprovals(request, tenantId);

        log.info("List approvals result: requestId={}, total={}, page={}",
                requestId, response.getTotal(), response.getPage());

        return ResponseEntity.ok(response);
    }

    /**
     * 获取审批任务详情
     *
     * 【功能说明】
     * 根据审批任务 ID 获取完整的审批详情，包括审批上下文、
     * 请求参数、执行状态等。用于审批人在决策前查看完整信息。
     *
     * 【权限要求】
     * - approval:read
     *
     * 【审计标记】
     * - 操作类型：QUERY
     * - 审计字段：tenantId, userId, approvalId
     *
     * @param id 审批任务 ID（UUID 格式）
     * @return 审批任务详情
     * @throws BusinessException 当审批任务不存在或无权访问时抛出
     */
    @GetMapping("/{id}")
    @PreAuthorize("hasRole('admin') or hasAuthority('approval:read')")
    public ResponseEntity<ApprovalTaskResponse> getApproval(@PathVariable String id) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Get approval: requestId={}, approvalId={}, tenant={}, user={}",
                requestId, id, tenantId, userId);

        ApprovalTaskResponse response = approvalService.getApproval(id, tenantId);

        log.info("Get approval result: requestId={}, approvalId={}, type={}, status={}",
                requestId, id, response.getTaskType(), response.getStatus());

        return ResponseEntity.ok(response);
    }

    /**
     * 通过审批
     *
     * 【功能说明】
     * 审批人同意执行该审批任务。审批通过后，系统将自动触发后续操作
     * （如工具执行、数据变更等）。此操作不可撤销。
     *
     * 【权限要求】
     * - approval:write
     * - 审批人需在审批任务的审批人列表中
     *
     * 【审计标记】
     * - 操作类型：APPROVE
     * - 审计字段：tenantId, reviewerId, approvalId, result
     * - 重要：此操作会写入审计日志，不可删除
     *
     * @param id 审批任务 ID（UUID 格式）
     * @param request 审批操作请求，可选包含审批备注
     * @return 更新后的审批任务状态
     * @throws BusinessException 当审批任务不存在、状态不允许审批或无权限时抛出
     */
    @PostMapping("/{id}/approve")
    @PreAuthorize("hasRole('admin') or hasAuthority('approval:approve')")
    @AuditLog(
        type = "tool.approved",
        category = "security",
        action = "通过审批",
        resourceType = "approval_task",
        severity = "warn",
        logArguments = true
    )
    public ResponseEntity<ApprovalTaskResponse> approveApproval(
            @PathVariable String id,
            @Valid @RequestBody(required = false) ApprovalActionRequest request) {

        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String reviewerId = tenantContextService.getCurrentUserId();

        log.info("Approve approval: requestId={}, approvalId={}, tenant={}, reviewer={}",
                requestId, id, tenantId, reviewerId);

        ApprovalTaskResponse response = approvalService.approve(id, request, reviewerId, tenantId);

        log.info("Approval approved: requestId={}, approvalId={}, status={}, reviewer={}",
                requestId, id, response.getStatus(), reviewerId);

        return ResponseEntity.ok(response);
    }

    /**
     * 拒绝审批
     *
     * 【功能说明】
     * 审批人拒绝执行该审批任务。审批拒绝后，关联的 Agent 执行将终止，
     * 并向用户返回拒绝原因。此操作不可撤销。
     *
     * 【权限要求】
     * - approval:write
     * - 审批人需在审批任务的审批人列表中
     *
     * 【审计标记】
     * - 操作类型：REJECT
     * - 审计字段：tenantId, reviewerId, approvalId, result, reason
     * - 重要：此操作会写入审计日志，不可删除
     *
     * @param id 审批任务 ID（UUID 格式）
     * @param request 审批操作请求，建议包含拒绝原因
     * @return 更新后的审批任务状态
     * @throws BusinessException 当审批任务不存在、状态不允许审批或无权限时抛出
     */
    @PostMapping("/{id}/reject")
    @PreAuthorize("hasRole('admin') or hasAuthority('approval:approve')")
    @AuditLog(
        type = "tool.rejected",
        category = "security",
        action = "拒绝审批",
        resourceType = "approval_task",
        severity = "warn",
        logArguments = true
    )
    public ResponseEntity<ApprovalTaskResponse> rejectApproval(
            @PathVariable String id,
            @Valid @RequestBody(required = false) ApprovalActionRequest request) {

        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String reviewerId = tenantContextService.getCurrentUserId();

        log.info("Reject approval: requestId={}, approvalId={}, tenant={}, reviewer={}",
                requestId, id, tenantId, reviewerId);

        ApprovalTaskResponse response = approvalService.reject(id, request, reviewerId, tenantId);

        log.info("Approval rejected: requestId={}, approvalId={}, status={}, reviewer={}",
                requestId, id, response.getStatus(), reviewerId);

        return ResponseEntity.ok(response);
    }
}