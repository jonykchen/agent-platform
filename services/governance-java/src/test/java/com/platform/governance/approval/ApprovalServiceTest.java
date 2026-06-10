package com.platform.governance.approval;

import com.platform.governance.notification.NotificationService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * ApprovalService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class ApprovalServiceTest {

    @Mock
    private ApprovalRepository approvalRepository;

    @Mock
    private NotificationService notificationService;

    private ApprovalService approvalService;

    @BeforeEach
    void setUp() {
        approvalService = new ApprovalService(approvalRepository, notificationService);
        // 注入默认审批人配置（@Value 字段在单测中需手动设置）
        ReflectionTestUtils.setField(approvalService, "defaultApprovers",
                List.of("alice", "bob"));
    }

    @Test
    @DisplayName("创建审批任务应分配审批人")
    void createApprovalTask_assignsApprover() {
        // When
        ApprovalTask result = approvalService.createApprovalTask(
                UUID.randomUUID(), UUID.randomUUID(), "tenant_001", "user_001", "reason");

        // Then：审批人应来自配置的默认列表
        assertNotNull(result.getAssigneeId());
        assertTrue(List.of("alice", "bob").contains(result.getAssigneeId()));
    }

    @Test
    @DisplayName("同一 runId 应稳定分配到同一审批人")
    void assignApprover_isStableForSameRunId() {
        UUID runId = UUID.randomUUID();

        ApprovalTask r1 = approvalService.createApprovalTask(
                runId, UUID.randomUUID(), "t", "u", "reason");
        ApprovalTask r2 = approvalService.createApprovalTask(
                runId, UUID.randomUUID(), "t", "u", "reason");

        assertEquals(r1.getAssigneeId(), r2.getAssigneeId());
    }

    @Test
    @DisplayName("超时审批任务应被自动拒绝并发布结果")
    void autoRejectExpiredApprovals_rejectsAndPublishes() {
        // Given：两个已过期的 pending 任务
        ApprovalTask expired1 = ApprovalTask.builder()
                .id(UUID.randomUUID()).runId(UUID.randomUUID())
                .status("pending").tenantId("t")
                .expiresAt(Instant.now().minusSeconds(10))
                .build();
        ApprovalTask expired2 = ApprovalTask.builder()
                .id(UUID.randomUUID()).runId(UUID.randomUUID())
                .status("pending").tenantId("t")
                .expiresAt(Instant.now().minusSeconds(20))
                .build();

        when(approvalRepository.findByStatusAndExpiresAtBefore(eq("pending"), any(Instant.class)))
                .thenReturn(List.of(expired1, expired2));

        // When
        approvalService.autoRejectExpiredApprovals();

        // Then：两个任务都被置为 rejected 并发布结果事件
        assertEquals("rejected", expired1.getStatus());
        assertEquals("rejected", expired2.getStatus());
        assertEquals("system", expired1.getReviewerId());
        verify(approvalRepository, times(2)).save(any(ApprovalTask.class));
        verify(notificationService, times(2)).publishApprovalResult(any(ApprovalTask.class));
    }

    @Test
    @DisplayName("无超时任务时不应触发任何操作")
    void autoRejectExpiredApprovals_noExpired_noOp() {
        when(approvalRepository.findByStatusAndExpiresAtBefore(eq("pending"), any(Instant.class)))
                .thenReturn(List.of());

        approvalService.autoRejectExpiredApprovals();

        verify(approvalRepository, never()).save(any());
        verify(notificationService, never()).publishApprovalResult(any());
    }

    @Test
    @DisplayName("创建审批任务应成功")
    void createApprovalTask_success() {
        // Given
        UUID runId = UUID.randomUUID();
        UUID toolInvocationId = UUID.randomUUID();
        String tenantId = "tenant_001";
        String userId = "user_001";
        String reason = "High risk operation";

        // When
        ApprovalTask result = approvalService.createApprovalTask(
                runId, toolInvocationId, tenantId, userId, reason);

        // Then
        assertNotNull(result);
        assertEquals(runId, result.getRunId());
        assertEquals(toolInvocationId, result.getToolInvocationId());
        assertEquals(tenantId, result.getTenantId());
        assertEquals(userId, result.getRequesterId());
        assertEquals("pending", result.getStatus());
        assertEquals(reason, result.getReason());
        assertNotNull(result.getId());
        assertNotNull(result.getExpiresAt());

        verify(approvalRepository).save(any(ApprovalTask.class));
        verify(notificationService).sendApprovalRequest(any(ApprovalTask.class));
    }

    @Test
    @DisplayName("创建审批任务应设置2小时过期时间")
    void createApprovalTask_setsExpiry2Hours() {
        // Given
        Instant beforeCreate = Instant.now();

        // When
        ApprovalTask result = approvalService.createApprovalTask(
                UUID.randomUUID(), UUID.randomUUID(), "tenant_001", "user_001", "reason");

        Instant afterCreate = Instant.now();

        // Then
        Instant expectedExpiryMin = beforeCreate.plusSeconds(7200);
        Instant expectedExpiryMax = afterCreate.plusSeconds(7200);

        assertTrue(result.getExpiresAt().isAfter(expectedExpiryMin.minusSeconds(1)));
        assertTrue(result.getExpiresAt().isBefore(expectedExpiryMax.plusSeconds(1)));
    }

    @Test
    @DisplayName("处理审批决策-批准应成功")
    void processDecision_approved_success() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        String reviewerId = "reviewer_001";

        ApprovalTask existingTask = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("pending")
                .tenantId("tenant_001")
                .build();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(existingTask));

        // When
        ApprovalTask result = approvalService.processDecision(
                approvalId, reviewerId, "approved", "Looks good");

        // Then
        assertEquals("approved", result.getStatus());
        assertEquals(reviewerId, result.getReviewerId());
        assertEquals("Looks good", result.getReviewComment());
        assertNotNull(result.getReviewedAt());

        verify(approvalRepository).save(any(ApprovalTask.class));
        verify(notificationService).publishApprovalResult(any(ApprovalTask.class));
    }

    @Test
    @DisplayName("处理审批决策-拒绝应成功")
    void processDecision_rejected_success() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        String reviewerId = "reviewer_001";

        ApprovalTask existingTask = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("pending")
                .tenantId("tenant_001")
                .build();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(existingTask));

        // When
        ApprovalTask result = approvalService.processDecision(
                approvalId, reviewerId, "rejected", "Insufficient justification");

        // Then
        assertEquals("rejected", result.getStatus());
        assertEquals(reviewerId, result.getReviewerId());
        assertEquals("Insufficient justification", result.getReviewComment());
        assertNotNull(result.getReviewedAt());
    }

    @Test
    @DisplayName("处理审批决策-审批不存在应抛出异常")
    void processDecision_approvalNotFound_throwsException() {
        // Given
        UUID approvalId = UUID.randomUUID();
        when(approvalRepository.findById(approvalId)).thenReturn(Optional.empty());

        // When & Then
        IllegalArgumentException exception = assertThrows(
                IllegalArgumentException.class,
                () -> approvalService.processDecision(approvalId, "reviewer_001", "approved", "comment"));

        assertTrue(exception.getMessage().contains("Approval not found"));
        verify(notificationService, never()).publishApprovalResult(any());
    }

    @Test
    @DisplayName("处理审批决策-已处理的审批应抛出异常")
    void processDecision_alreadyProcessed_throwsException() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();

        ApprovalTask alreadyApprovedTask = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("approved")
                .tenantId("tenant_001")
                .build();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(alreadyApprovedTask));

        // When & Then
        IllegalStateException exception = assertThrows(
                IllegalStateException.class,
                () -> approvalService.processDecision(approvalId, "reviewer_001", "approved", "comment"));

        assertTrue(exception.getMessage().contains("already processed"));
        verify(notificationService, never()).publishApprovalResult(any());
    }

    @Test
    @DisplayName("处理审批决策-已拒绝的审批不能再处理")
    void processDecision_alreadyRejected_throwsException() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();

        ApprovalTask alreadyRejectedTask = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("rejected")
                .tenantId("tenant_001")
                .build();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(alreadyRejectedTask));

        // When & Then
        assertThrows(IllegalStateException.class,
                () -> approvalService.processDecision(approvalId, "reviewer_001", "approved", "comment"));
    }

    @Test
    @DisplayName("创建审批任务应发送通知")
    void createApprovalTask_sendsNotification() {
        // Given
        UUID runId = UUID.randomUUID();
        ArgumentCaptor<ApprovalTask> taskCaptor = ArgumentCaptor.forClass(ApprovalTask.class);

        // When
        approvalService.createApprovalTask(runId, UUID.randomUUID(), "tenant_001", "user_001", "reason");

        // Then
        verify(notificationService).sendApprovalRequest(taskCaptor.capture());
        ApprovalTask capturedTask = taskCaptor.getValue();
        assertEquals(runId, capturedTask.getRunId());
        assertEquals("tenant_001", capturedTask.getTenantId());
    }

    @Test
    @DisplayName("批准审批任务应发布结果事件")
    void processDecision_publishesResultEvent() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        ApprovalTask existingTask = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("pending")
                .tenantId("tenant_001")
                .build();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(existingTask));

        ArgumentCaptor<ApprovalTask> taskCaptor = ArgumentCaptor.forClass(ApprovalTask.class);

        // When
        approvalService.processDecision(approvalId, "reviewer_001", "approved", "comment");

        // Then
        verify(notificationService).publishApprovalResult(taskCaptor.capture());
        assertEquals("approved", taskCaptor.getValue().getStatus());
    }

    @Test
    @DisplayName("创建审批任务应生成UUID作为ID")
    void createApprovalTask_generatesUuidId() {
        // When
        ApprovalTask result1 = approvalService.createApprovalTask(
                UUID.randomUUID(), UUID.randomUUID(), "tenant_001", "user_001", "reason");
        ApprovalTask result2 = approvalService.createApprovalTask(
                UUID.randomUUID(), UUID.randomUUID(), "tenant_001", "user_001", "reason");

        // Then
        assertNotNull(result1.getId());
        assertNotNull(result2.getId());
        assertNotEquals(result1.getId(), result2.getId());
    }

    @Test
    @DisplayName("创建审批任务应保留所有参数")
    void createApprovalTask_preservesAllParameters() {
        // Given
        UUID runId = UUID.randomUUID();
        UUID toolInvocationId = UUID.randomUUID();
        String tenantId = "tenant_test";
        String userId = "user_test";
        String reason = "Test reason for approval";

        // When
        ApprovalTask result = approvalService.createApprovalTask(
                runId, toolInvocationId, tenantId, userId, reason);

        // Then
        assertEquals(runId, result.getRunId());
        assertEquals(toolInvocationId, result.getToolInvocationId());
        assertEquals(tenantId, result.getTenantId());
        assertEquals(userId, result.getRequesterId());
        assertEquals(reason, result.getReason());
    }

    @Test
    @DisplayName("处理审批决策应记录审核人ID")
    void processDecision_recordsReviewerId() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        ApprovalTask existingTask = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("pending")
                .tenantId("tenant_001")
                .build();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(existingTask));

        // When
        ApprovalTask result = approvalService.processDecision(
                approvalId, "reviewer_xyz", "approved", "comment");

        // Then
        assertEquals("reviewer_xyz", result.getReviewerId());
    }

    @Test
    @DisplayName("处理审批决策应记录审核时间")
    void processDecision_recordsReviewedAt() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        ApprovalTask existingTask = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("pending")
                .tenantId("tenant_001")
                .build();

        when(approvalRepository.findById(approvalId)).thenReturn(Optional.of(existingTask));

        Instant beforeProcess = Instant.now();

        // When
        ApprovalTask result = approvalService.processDecision(
                approvalId, "reviewer_001", "approved", "comment");

        Instant afterProcess = Instant.now();

        // Then
        assertNotNull(result.getReviewedAt());
        assertTrue(result.getReviewedAt().isAfter(beforeProcess.minusSeconds(1)));
        assertTrue(result.getReviewedAt().isBefore(afterProcess.plusSeconds(1)));
    }
}
