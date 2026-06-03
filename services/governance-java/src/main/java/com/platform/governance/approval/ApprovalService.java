package com.platform.governance.approval;

import com.platform.governance.notification.NotificationService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.UUID;

/**
 * 审批流程服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApprovalService {

    private final ApprovalRepository approvalRepository;
    private final NotificationService notificationService;

    /**
     * 创建审批任务
     */
    public ApprovalTask createApprovalTask(UUID runId, UUID toolInvocationId,
            String tenantId, String userId, String reason) {

        UUID approvalId = UUID.randomUUID();

        ApprovalTask task = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .toolInvocationId(toolInvocationId)
                .tenantId(tenantId)
                .requesterId(userId)
                .status("pending")
                .reason(reason)
                .expiresAt(Instant.now().plusSeconds(7200)) // 2小时过期
                .build();

        approvalRepository.save(task);

        // 发送通知
        notificationService.sendApprovalRequest(task);

        log.info("Created approval task: approvalId={}, runId={}", approvalId, runId);

        return task;
    }

    /**
     * 处理审批决策
     */
    public ApprovalTask processDecision(UUID approvalId, String reviewerId,
            String decision, String comment) {

        ApprovalTask task = approvalRepository.findById(approvalId)
                .orElseThrow(() -> new IllegalArgumentException("Approval not found: " + approvalId));

        if (!"pending".equals(task.getStatus())) {
            throw new IllegalStateException("Approval already processed: " + task.getStatus());
        }

        task.setReviewerId(reviewerId);
        task.setReviewComment(comment);
        task.setReviewedAt(Instant.now());
        task.setProcessedAt(Instant.now());
        task.setStatus(decision); // approved / rejected

        approvalRepository.save(task);

        // 发布审批结果事件（通过 Kafka）
        notificationService.publishApprovalResult(task);

        log.info("Processed approval decision: approvalId={}, decision={}", approvalId, decision);

        return task;
    }
}
