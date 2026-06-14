package com.platform.governance.approval;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * 审批管理 REST 控制器
 *
 * <p>暴露审批创建和决策 API，供 Gateway 代理调用。
 *
 * <h2>安全说明</h2>
 * <ul>
 *   <li>创建审批：需要 SERVICE 角色（内部服务调用）</li>
 *   <li>审批决策：需要 APPROVER 角色，且 reviewerId 必须为当前认证用户</li>
 * </ul>
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/approvals")
@RequiredArgsConstructor
public class ApprovalController {

    private final ApprovalService approvalService;

    /**
     * 创建审批任务
     */
    @PostMapping
    @PreAuthorize("hasRole('SERVICE')")
    public ResponseEntity<Map<String, Object>> createApproval(@RequestBody CreateApprovalRequest request) {
        ApprovalTask task = approvalService.createApprovalTask(
            request.runId(),
            request.toolInvocationId(),
            request.tenantId(),
            request.userId(),
            request.reason()
        );

        return ResponseEntity.ok(Map.of(
            "approval_id", task.getId().toString(),
            "assignee_id", task.getAssigneeId(),
            "status", task.getStatus(),
            "expires_at", task.getExpiresAt().toString()
        ));
    }

    /**
     * 处理审批决策
     *
     * <p>reviewerId 从认证上下文提取，防止越权操作。
     */
    @PostMapping("/{approvalId}/decision")
    @PreAuthorize("hasRole('APPROVER')")
    public ResponseEntity<Map<String, Object>> processDecision(
            @PathVariable UUID approvalId,
            @RequestBody DecisionRequest request,
            Authentication auth) {

        // 从认证上下文提取 reviewerId，不接受请求参数传入
        String reviewerId = auth.getName();

        ApprovalTask task = approvalService.processDecision(
            approvalId, reviewerId, request.decision(), request.comment()
        );

        return ResponseEntity.ok(Map.of(
            "approval_id", task.getId().toString(),
            "status", task.getStatus()
        ));
    }

    /**
     * 查询审批任务状态
     */
    @GetMapping("/{approvalId}")
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<Map<String, Object>> getApproval(@PathVariable UUID approvalId) {
        return approvalService.findById(approvalId)
            .map(task -> ResponseEntity.<Map<String, Object>>ok(Map.of(
                "approval_id", task.getId().toString(),
                "run_id", task.getRunId().toString(),
                "status", task.getStatus(),
                "assignee_id", task.getAssigneeId() != null ? task.getAssigneeId() : "",
                "reason", task.getReason() != null ? task.getReason() : "",
                "created_at", task.getCreatedAt().toString(),
                "expires_at", task.getExpiresAt().toString()
            )))
            .orElse(ResponseEntity.notFound().build());
    }

    /**
     * 创建审批请求 DTO
     */
    public record CreateApprovalRequest(
        UUID runId,
        UUID toolInvocationId,
        String tenantId,
        String userId,
        String reason
    ) {}

    /**
     * 审批决策请求 DTO
     */
    public record DecisionRequest(
        String decision,  // approved / rejected
        String comment
    ) {}
}
