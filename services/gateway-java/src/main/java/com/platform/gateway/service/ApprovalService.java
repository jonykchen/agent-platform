package com.platform.gateway.service;

import com.platform.gateway.dto.request.ApprovalActionRequest;
import com.platform.gateway.dto.request.ApprovalListRequest;
import com.platform.gateway.dto.response.ApprovalTaskResponse;
import com.platform.gateway.dto.response.PagedResponse;
import com.platform.gateway.entity.ApprovalTask;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.ApprovalTaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * 审批服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApprovalService {

    private final ApprovalTaskRepository approvalTaskRepository;

    /**
     * 查询审批列表
     */
    public PagedResponse<ApprovalTaskResponse> listApprovals(ApprovalListRequest request, String tenantId) {
        // 构建分页参数
        int pageNumber = request.getPage() != null ? request.getPage() - 1 : 0;
        int pageSize = request.getPage_size() != null ? request.getPage_size() : 10;

        String sortBy = request.getSort_by() != null ? request.getSort_by() : "createdAt";
        boolean ascending = "asc".equalsIgnoreCase(request.getSort_order());
        Sort.Direction direction = ascending ? Sort.Direction.ASC : Sort.Direction.DESC;
        Sort sort = mapSortField(sortBy, direction);

        Pageable pageable = PageRequest.of(pageNumber, pageSize, sort);

        // 查询
        Page<ApprovalTask> page = approvalTaskRepository.findByConditions(
                tenantId,
                request.getStatus(),
                request.getPriority(),
                request.getTask_type(),
                null, // assigneeId
                pageable
        );

        // 转换响应
        List<ApprovalTaskResponse> items = page.getContent().stream()
                .map(this::toResponse)
                .toList();

        return PagedResponse.<ApprovalTaskResponse>builder()
                .items(items)
                .total(page.getTotalElements())
                .page(request.getPage() != null ? request.getPage() : 1)
                .page_size(pageSize)
                .total_pages(page.getTotalPages())
                .build();
    }

    /**
     * 获取审批详情
     */
    public ApprovalTaskResponse getApproval(String approvalId, String tenantId) {
        UUID id = parseUUID(approvalId, "审批ID格式错误");

        ApprovalTask task = approvalTaskRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_APPROVAL_NOT_FOUND, "审批任务不存在"));

        return toResponse(task);
    }

    /**
     * 通过审批
     */
    @Transactional
    public ApprovalTaskResponse approve(String approvalId, ApprovalActionRequest request, String reviewerId, String tenantId) {
        UUID id = parseUUID(approvalId, "审批ID格式错误");

        ApprovalTask task = approvalTaskRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_APPROVAL_NOT_FOUND, "审批任务不存在"));

        // 状态校验
        if (!"pending".equals(task.getStatus())) {
            throw new BusinessException(ErrorCode.ERR_APPROVAL_ALREADY_REVIEWED, "审批已处理");
        }

        // 过期检查
        if (task.getExpiresAt() != null && Instant.now().isAfter(task.getExpiresAt())) {
            task.setStatus("expired");
            approvalTaskRepository.save(task);
            throw new BusinessException(ErrorCode.ERR_APPROVAL_EXPIRED, "审批已过期");
        }

        // 更新审批状态
        task.setStatus("approved");
        task.setReviewerId(reviewerId);
        task.setReviewComment(request != null ? request.getComment() : null);
        task.setReviewedAt(Instant.now());

        task = approvalTaskRepository.save(task);

        log.info("Approval approved: approvalId={}, reviewerId={}", approvalId, reviewerId);

        return toResponse(task);
    }

    /**
     * 拒绝审批
     */
    @Transactional
    public ApprovalTaskResponse reject(String approvalId, ApprovalActionRequest request, String reviewerId, String tenantId) {
        UUID id = parseUUID(approvalId, "审批ID格式错误");

        ApprovalTask task = approvalTaskRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_APPROVAL_NOT_FOUND, "审批任务不存在"));

        // 状态校验
        if (!"pending".equals(task.getStatus())) {
            throw new BusinessException(ErrorCode.ERR_APPROVAL_ALREADY_REVIEWED, "审批已处理");
        }

        // 过期检查
        if (task.getExpiresAt() != null && Instant.now().isAfter(task.getExpiresAt())) {
            task.setStatus("expired");
            approvalTaskRepository.save(task);
            throw new BusinessException(ErrorCode.ERR_APPROVAL_EXPIRED, "审批已过期");
        }

        // 更新审批状态
        task.setStatus("rejected");
        task.setReviewerId(reviewerId);
        task.setReviewComment(request != null ? request.getComment() : null);
        task.setReviewedAt(Instant.now());

        task = approvalTaskRepository.save(task);

        log.info("Approval rejected: approvalId={}, reviewerId={}", approvalId, reviewerId);

        return toResponse(task);
    }

    /**
     * 创建审批任务
     */
    @Transactional
    public ApprovalTaskResponse createApprovalTask(ApprovalTask task) {
        task = approvalTaskRepository.save(task);
        log.info("Approval task created: id={}, tenantId={}, type={}",
                task.getId(), task.getTenantId(), task.getTaskType());
        return toResponse(task);
    }

    /**
     * 批量标记过期审批
     */
    @Transactional
    public int markExpiredApprovals() {
        List<ApprovalTask> expiredTasks = approvalTaskRepository.findExpiredPendingApprovals(Instant.now());
        for (ApprovalTask task : expiredTasks) {
            task.setStatus("expired");
        }
        approvalTaskRepository.saveAll(expiredTasks);
        log.info("Marked {} approval tasks as expired", expiredTasks.size());
        return expiredTasks.size();
    }

    // ========== 辅助方法 ==========

    private ApprovalTaskResponse toResponse(ApprovalTask task) {
        return ApprovalTaskResponse.builder()
                .id(task.getId().toString())
                .run_id(task.getRunId() != null ? task.getRunId().toString() : null)
                .tool_invocation_id(task.getToolInvocationId() != null ? task.getToolInvocationId().toString() : null)
                .tenant_id(task.getTenantId())
                .task_type(task.getTaskType())
                .title(task.getTitle())
                .description(task.getDescription())
                .request_context(task.getRequestContext())
                .requester_id(task.getRequesterId())
                .assignee_id(task.getAssigneeId())
                .priority(task.getPriority())
                .status(task.getStatus())
                .reviewer_id(task.getReviewerId())
                .review_comment(task.getReviewComment())
                .reviewed_at(task.getReviewedAt())
                .expires_at(task.getExpiresAt())
                .created_at(task.getCreatedAt())
                .updated_at(task.getUpdatedAt())
                .build();
    }

    private Sort mapSortField(String sortBy, Sort.Direction direction) {
        String fieldName;
        switch (sortBy) {
            case "priority":
                fieldName = "priority";
                // 优先级排序需要特殊处理：urgent > high > normal > low
                // 这里用权重计算，但 JPA 排序不支持表达式，所以先按字段排序
                break;
            case "expires_at":
                fieldName = "expiresAt";
                break;
            case "created_at":
            default:
                fieldName = "createdAt";
                break;
        }
        return Sort.by(direction, fieldName);
    }

    private UUID parseUUID(String str, String errorMessage) {
        try {
            return UUID.fromString(str);
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.ERR_INVALID_REQUEST, errorMessage);
        }
    }
}
