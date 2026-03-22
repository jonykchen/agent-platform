package com.platform.gateway.controller;

import com.platform.gateway.dto.request.ApprovalActionRequest;
import com.platform.gateway.dto.request.ApprovalListRequest;
import com.platform.gateway.dto.response.ApprovalTaskResponse;
import com.platform.gateway.dto.response.PagedResponse;
import com.platform.gateway.service.ApprovalService;
import com.platform.gateway.service.TenantContextService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * 审批控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/approvals")
@RequiredArgsConstructor
public class ApprovalController {

    private final ApprovalService approvalService;
    private final TenantContextService tenantContextService;

    /**
     * 获取审批列表
     */
    @GetMapping
    public ResponseEntity<PagedResponse<ApprovalTaskResponse>> listApprovals(ApprovalListRequest request) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("List approvals: tenant={}, user={}, status={}, page={}, pageSize={}",
                tenantId, userId, request.getStatus(), request.getPage(), request.getPage_size());

        PagedResponse<ApprovalTaskResponse> response = approvalService.listApprovals(request, tenantId);

        log.info("List approvals result: total={}, page={}", response.getTotal(), response.getPage());

        return ResponseEntity.ok(response);
    }

    /**
     * 获取审批详情
     */
    @GetMapping("/{id}")
    public ResponseEntity<ApprovalTaskResponse> getApproval(@PathVariable String id) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Get approval: approvalId={}, tenant={}, user={}", id, tenantId, userId);

        ApprovalTaskResponse response = approvalService.getApproval(id, tenantId);

        return ResponseEntity.ok(response);
    }

    /**
     * 通过审批
     */
    @PostMapping("/{id}/approve")
    public ResponseEntity<ApprovalTaskResponse> approveApproval(
            @PathVariable String id,
            @Valid @RequestBody(required = false) ApprovalActionRequest request) {

        String tenantId = tenantContextService.getCurrentTenantId();
        String reviewerId = tenantContextService.getCurrentUserId();

        log.info("Approve approval: approvalId={}, tenant={}, reviewer={}", id, tenantId, reviewerId);

        ApprovalTaskResponse response = approvalService.approve(id, request, reviewerId, tenantId);

        log.info("Approval approved: approvalId={}, status={}", id, response.getStatus());

        return ResponseEntity.ok(response);
    }

    /**
     * 拒绝审批
     */
    @PostMapping("/{id}/reject")
    public ResponseEntity<ApprovalTaskResponse> rejectApproval(
            @PathVariable String id,
            @Valid @RequestBody(required = false) ApprovalActionRequest request) {

        String tenantId = tenantContextService.getCurrentTenantId();
        String reviewerId = tenantContextService.getCurrentUserId();

        log.info("Reject approval: approvalId={}, tenant={}, reviewer={}", id, tenantId, reviewerId);

        ApprovalTaskResponse response = approvalService.reject(id, request, reviewerId, tenantId);

        log.info("Approval rejected: approvalId={}, status={}", id, response.getStatus());

        return ResponseEntity.ok(response);
    }
}
