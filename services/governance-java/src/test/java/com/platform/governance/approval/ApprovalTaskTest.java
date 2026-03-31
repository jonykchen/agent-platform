package com.platform.governance.approval;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;

import static org.junit.jupiter.api.Assertions.*;

/**
 * ApprovalTask entity unit tests
 */
class ApprovalTaskTest {

    @Test
    @DisplayName("should_build_task_with_all_fields")
    void builder_shouldCreateCompleteTask() {
        // Given
        Instant now = Instant.now();
        Instant expiresAt = now.plus(2, ChronoUnit.HOURS);

        // When
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .runId("run_456")
                .toolInvocationId("tool_inv_789")
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
        assertEquals("approval_123", task.getId());
        assertEquals("run_456", task.getRunId());
        assertEquals("tool_inv_789", task.getToolInvocationId());
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
        // When
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .runId("run_456")
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
        Instant now = Instant.now();

        // When
        task.setId("new_id");
        task.setRunId("new_run");
        task.setToolInvocationId("new_tool_inv");
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
        assertEquals("new_id", task.getId());
        assertEquals("new_run", task.getRunId());
        assertEquals("new_tool_inv", task.getToolInvocationId());
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
    @DisplayName("should_build_empty_task")
    void emptyBuilder_shouldCreateEmptyTask() {
        // When
        ApprovalTask task = ApprovalTask.builder().build();

        // Then
        assertNull(task.getId());
        assertNull(task.getStatus());
    }

    @Test
    @DisplayName("should_handle_equality_correctly")
    void equality_shouldWorkCorrectly() {
        // Given
        ApprovalTask task1 = ApprovalTask.builder().id("approval_123").build();
        ApprovalTask task2 = ApprovalTask.builder().id("approval_123").build();
        ApprovalTask task3 = ApprovalTask.builder().id("approval_456").build();

        // When & Then
        assertEquals(task1, task2);
        assertNotEquals(task1, task3);
        assertEquals(task1.hashCode(), task2.hashCode());
    }

    @Test
    @DisplayName("should_generate_string_representation")
    void toString_shouldContainFields() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .status("pending")
                .build();

        // When
        String str = task.toString();

        // Then
        assertTrue(str.contains("approval_123"));
        assertTrue(str.contains("pending"));
    }
}
