package com.platform.governance.approval;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

/**
 * ApprovalTask entity unit tests
 */
class ApprovalTaskTest {

    @Test
    @DisplayName("should_build_task_with_all_fields")
    void builder_shouldCreateCompleteTask() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();
        UUID toolInvocationId = UUID.randomUUID();
        Instant now = Instant.now();
        Instant expiresAt = now.plus(2, ChronoUnit.HOURS);

        // When
        ApprovalTask task = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .toolInvocationId(toolInvocationId)
                .tenantId("tenant_001")
                .requesterId("user_001")
                .assigneeId("approver_001")
                .status("pending")
                .reason("High value transaction requires approval")
                .reviewComment("Looks legitimate")
                .reviewerId("reviewer_001")
                .createdAt(now)
                .expiresAt(expiresAt)
                .reviewedAt(now.plus(30, ChronoUnit.MINUTES))
                .build();

        // Then
        assertEquals(approvalId, task.getId());
        assertEquals(runId, task.getRunId());
        assertEquals(toolInvocationId, task.getToolInvocationId());
        assertEquals("tenant_001", task.getTenantId());
        assertEquals("user_001", task.getRequesterId());
        assertEquals("approver_001", task.getAssigneeId());
        assertEquals("pending", task.getStatus());
        assertEquals("High value transaction requires approval", task.getReason());
        assertEquals("Looks legitimate", task.getReviewComment());
        assertEquals("reviewer_001", task.getReviewerId());
        assertEquals(now, task.getCreatedAt());
        assertEquals(expiresAt, task.getExpiresAt());
    }

    @Test
    @DisplayName("should_allow_null_optional_fields")
    void builder_withNullFields_shouldSucceed() {
        // Given
        UUID approvalId = UUID.randomUUID();
        UUID runId = UUID.randomUUID();

        // When
        ApprovalTask task = ApprovalTask.builder()
                .id(approvalId)
                .runId(runId)
                .status("pending")
                .build();

        // Then
        assertNull(task.getTenantId());
        assertNull(task.getRequesterId());
        assertNull(task.getAssigneeId());
        assertNull(task.getReason());
        assertNull(task.getReviewComment());
        assertNull(task.getReviewerId());
        assertNull(task.getCreatedAt());
        assertNull(task.getExpiresAt());
        assertNull(task.getReviewedAt());
    }

    @Test
    @DisplayName("should_allow_modification_via_setters")
    void setters_shouldModifyFields() {
        // Given
        ApprovalTask task = ApprovalTask.builder().build();
        UUID newId = UUID.randomUUID();
        UUID newRunId = UUID.randomUUID();
        UUID newToolInvId = UUID.randomUUID();
        Instant now = Instant.now();

        // When
        task.setId(newId);
        task.setRunId(newRunId);
        task.setToolInvocationId(newToolInvId);
        task.setTenantId("new_tenant");
        task.setRequesterId("new_user");
        task.setAssigneeId("new_assignee");
        task.setStatus("approved");
        task.setReason("New reason");
        task.setReviewComment("New comment");
        task.setReviewerId("new_reviewer");
        task.setCreatedAt(now);
        task.setExpiresAt(now.plusSeconds(7200));
        task.setReviewedAt(now.plusSeconds(1800));

        // Then
        assertEquals(newId, task.getId());
        assertEquals(newRunId, task.getRunId());
        assertEquals(newToolInvId, task.getToolInvocationId());
        assertEquals("new_tenant", task.getTenantId());
        assertEquals("new_user", task.getRequesterId());
        assertEquals("new_assignee", task.getAssigneeId());
        assertEquals("approved", task.getStatus());
        assertEquals("New reason", task.getReason());
        assertEquals("New comment", task.getReviewComment());
        assertEquals("new_reviewer", task.getReviewerId());
    }

    @Test
    @DisplayName("should_support_common_status_values")
    void status_shouldSupportAllValues() {
        // Given
        ApprovalTask task = ApprovalTask.builder().build();
        String[] validStatuses = {"pending", "approved", "rejected", "expired", "cancelled"};

        for (String status : validStatuses) {
            // When
            task.setStatus(status);

            // Then
            assertEquals(status, task.getStatus());
        }
    }

    @Test
    @DisplayName("should_build_empty_task_with_defaults")
    void emptyBuilder_shouldCreateEmptyTaskWithDefaults() {
        // When
        ApprovalTask task = ApprovalTask.builder().build();

        // Then
        assertNull(task.getId());
        assertEquals("pending", task.getStatus()); // Default value from @Builder.Default
    }

    @Test
    @DisplayName("should_handle_equality_correctly")
    void equality_shouldWorkCorrectly() {
        // Given
        UUID approvalId = UUID.randomUUID();
        ApprovalTask task1 = ApprovalTask.builder().id(approvalId).build();
        ApprovalTask task2 = ApprovalTask.builder().id(approvalId).build();
        ApprovalTask task3 = ApprovalTask.builder().id(UUID.randomUUID()).build();

        // When & Then
        assertEquals(task1, task2);
        assertNotEquals(task1, task3);
        assertEquals(task1.hashCode(), task2.hashCode());
    }

    @Test
    @DisplayName("should_generate_string_representation")
    void toString_shouldContainFields() {
        // Given
        UUID approvalId = UUID.randomUUID();
        ApprovalTask task = ApprovalTask.builder()
                .id(approvalId)
                .status("pending")
                .build();

        // When
        String str = task.toString();

        // Then
        assertTrue(str.contains(approvalId.toString()));
        assertTrue(str.contains("pending"));
    }
}
