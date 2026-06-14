package com.platform.governance.approval;

import com.platform.governance.notification.NotificationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 审批流程服务
 *
 * <p>负责审批任务的创建、审批人分配、决策处理与超时自动拒绝，是审批闭环
 * （Gateway 风险评估 → Tool Bus 拦截 → 人工审批 → 恢复执行）的治理侧核心。
 */
@Slf4j
@Service
public class ApprovalService {

    /** 审批等待超时（秒），对齐 APPROVAL_WAIT_TIMEOUT_S=7200（2 小时） */
    private static final long APPROVAL_TIMEOUT_SECONDS = 7200;

    private final ApprovalRepository approvalRepository;
    private final NotificationService notificationService;

    /**
     * 默认审批人列表（逗号分隔，由配置注入）。
     *
     * <p>生产环境通过 {@code APPROVAL_DEFAULT_APPROVERS} 指定。按 runId 哈希
     * 做简单轮询分配，避免所有任务压给同一人。后续可扩展为按租户/风险等级
     * 路由到不同审批组。
     */
    @Value("${approval.default-approvers:admin}")
    private List<String> defaultApprovers;

    public ApprovalService(ApprovalRepository approvalRepository,
                           NotificationService notificationService) {
        this.approvalRepository = approvalRepository;
        this.notificationService = notificationService;
    }

    /**
     * 根据 ID 查询审批任务
     */
    public Optional<ApprovalTask> findById(UUID approvalId) {
        return approvalRepository.findById(approvalId);
    }

    /**
     * 创建审批任务（含审批人分配）
     */
    public ApprovalTask createApprovalTask(UUID runId, UUID toolInvocationId,
            String tenantId, String userId, String reason) {

        UUID approvalId = UUID.randomUUID();
        String assignee = assignApprover(runId);

        ApprovalTask task = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .toolInvocationId(toolInvocationId)
                .tenantId(tenantId)
                .requesterId(userId)
                .assigneeId(assignee)
                .status("pending")
                .reason(reason)
                .expiresAt(Instant.now().plusSeconds(APPROVAL_TIMEOUT_SECONDS))
                .build();

        approvalRepository.save(task);

        // 发送通知（通知到分配的审批人）
        notificationService.sendApprovalRequest(task);

        log.info("Created approval task: approvalId={}, runId={}, assignee={}",
                approvalId, runId, assignee);

        return task;
    }

    /**
     * 分配审批人：按 runId 哈希在默认审批人列表中轮询选择。
     */
    private String assignApprover(UUID runId) {
        if (defaultApprovers == null || defaultApprovers.isEmpty()) {
            return "admin";
        }
        int index = Math.floorMod(runId.hashCode(), defaultApprovers.size());
        return defaultApprovers.get(index).trim();
    }

    /**
     * 审批超时自动拒绝。
     *
     * <p>每分钟扫描一次，将已过期仍处于 pending 的审批任务自动置为 rejected，
     * 并发布审批结果事件，使被中断的 Agent 运行得以恢复（拒绝路径），
     * 避免请求永久挂起。
     */
    @Scheduled(fixedDelayString = "${approval.timeout-scan-interval-ms:60000}")
    @Transactional
    public void autoRejectExpiredApprovals() {
        List<ApprovalTask> expired =
                approvalRepository.findByStatusAndExpiresAtBefore("pending", Instant.now());
        if (expired.isEmpty()) {
            return;
        }

        for (ApprovalTask task : expired) {
            task.setStatus("rejected");
            task.setReviewerId("system");
            task.setReviewComment("审批超时自动拒绝");
            task.setReviewedAt(Instant.now());
            task.setProcessedAt(Instant.now());
            approvalRepository.save(task);
            notificationService.publishApprovalResult(task);
            log.warn("Approval auto-rejected on timeout: approvalId={}, runId={}",
                    task.getId(), task.getRunId());
        }

        log.info("Auto-rejected {} expired approval tasks", expired.size());
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

        // 校验审批人身份：只有指定的审批人才能处理此任务
        if (!task.getAssigneeId().equals(reviewerId)) {
            throw new IllegalArgumentException(
                "Reviewer '" + reviewerId + "' is not the assigned approver for approval " + approvalId
                + ". Assigned to: " + task.getAssigneeId()
            );
        }

        // 校验审批是否已过期
        if (task.getExpiresAt() != null && task.getExpiresAt().isBefore(Instant.now())) {
            throw new IllegalStateException("Approval has expired: " + approvalId);
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
