package com.platform.toolbus.executor;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * ToolExecutionResult unit tests
 */
class ToolExecutionResultTest {

    @Test
    @DisplayName("should_build_result_with_all_fields")
    void builder_shouldCreateCompleteResult() {
        // When
        ToolExecutionResult result = ToolExecutionResult.builder()
                .callId("call_123")
                .status("success")
                .resultJson("{\"key\": \"value\"}")
                .approvalId("approval_456")
                .riskLevel("low")
                .wasCached(true)
                .durationMs(150)
                .providerLatencyMs(100)
                .errorCode(null)
                .errorMessage(null)
                .build();

        // Then
        assertEquals("call_123", result.getCallId());
        assertEquals("success", result.getStatus());
        assertEquals("{\"key\": \"value\"}", result.getResultJson());
        assertEquals("approval_456", result.getApprovalId());
        assertEquals("low", result.getRiskLevel());
        assertTrue(result.isWasCached());
        assertEquals(150, result.getDurationMs());
        assertEquals(100, result.getProviderLatencyMs());
        assertNull(result.getErrorCode());
        assertNull(result.getErrorMessage());
    }

    @Test
    @DisplayName("should_build_failed_result_with_error_info")
    void builder_withError_shouldCreateFailedResult() {
        // When
        ToolExecutionResult result = ToolExecutionResult.builder()
                .callId("call_456")
                .status("failed")
                .errorCode("ERR_TOOL_EXECUTION_FAILED")
                .errorMessage("Connection timeout")
                .durationMs(30000)
                .build();

        // Then
        assertEquals("failed", result.getStatus());
        assertEquals("ERR_TOOL_EXECUTION_FAILED", result.getErrorCode());
        assertEquals("Connection timeout", result.getErrorMessage());
        assertNull(result.getResultJson());
    }

    @Test
    @DisplayName("should_support_all_status_values")
    void status_shouldSupportAllValues() {
        // Given
        ToolExecutionResult result = ToolExecutionResult.builder().build();
        String[] validStatuses = {"pending", "success", "failed", "rejected", "pending_approval", "timeout"};

        for (String status : validStatuses) {
            // When
            result.setStatus(status);

            // Then
            assertEquals(status, result.getStatus());
        }
    }

    @Test
    @DisplayName("should_allow_null_optional_fields")
    void builder_withNullFields_shouldSucceed() {
        // When
        ToolExecutionResult result = ToolExecutionResult.builder()
                .callId("call_789")
                .status("pending")
                .build();

        // Then
        assertNull(result.getResultJson());
        assertNull(result.getApprovalId());
        assertNull(result.getRiskLevel());
        assertFalse(result.isWasCached());
        assertEquals(0, result.getDurationMs());
        assertEquals(0, result.getProviderLatencyMs());
    }

    @Test
    @DisplayName("should_allow_modification_via_setters")
    void setters_shouldModifyFields() {
        // Given
        ToolExecutionResult result = ToolExecutionResult.builder().build();

        // When
        result.setCallId("new_call");
        result.setStatus("approved");
        result.setResultJson("{\"new\": true}");
        result.setApprovalId("new_approval");
        result.setRiskLevel("high");
        result.setWasCached(false);
        result.setDurationMs(200);
        result.setProviderLatencyMs(150);
        result.setErrorCode("ERR_CUSTOM");
        result.setErrorMessage("Custom error");

        // Then
        assertEquals("new_call", result.getCallId());
        assertEquals("approved", result.getStatus());
        assertEquals("{\"new\": true}", result.getResultJson());
        assertEquals("new_approval", result.getApprovalId());
        assertEquals("high", result.getRiskLevel());
        assertFalse(result.isWasCached());
        assertEquals(200, result.getDurationMs());
        assertEquals(150, result.getProviderLatencyMs());
        assertEquals("ERR_CUSTOM", result.getErrorCode());
        assertEquals("Custom error", result.getErrorMessage());
    }

    @Test
    @DisplayName("should_build_empty_result")
    void emptyBuilder_shouldCreateEmptyResult() {
        // When
        ToolExecutionResult result = ToolExecutionResult.builder().build();

        // Then
        assertNull(result.getCallId());
        assertNull(result.getStatus());
    }

    @Test
    @DisplayName("should_handle_equality_correctly")
    void equality_shouldWorkCorrectly() {
        // Given
        ToolExecutionResult result1 = ToolExecutionResult.builder()
                .callId("call_123")
                .status("success")
                .build();
        ToolExecutionResult result2 = ToolExecutionResult.builder()
                .callId("call_123")
                .status("success")
                .build();
        ToolExecutionResult result3 = ToolExecutionResult.builder()
                .callId("call_456")
                .status("success")
                .build();

        // When & Then
        assertEquals(result1, result2);
        assertNotEquals(result1, result3);
        assertEquals(result1.hashCode(), result2.hashCode());
    }

    @Test
    @DisplayName("should_generate_string_representation")
    void toString_shouldContainFields() {
        // Given
        ToolExecutionResult result = ToolExecutionResult.builder()
                .callId("call_123")
                .status("success")
                .build();

        // When
        String str = result.toString();

        // Then
        assertTrue(str.contains("call_123"));
        assertTrue(str.contains("success"));
    }

    @Test
    @DisplayName("should_handle_negative_duration_for_edge_cases")
    void durationMs_canBeZeroOrPositive() {
        // Given
        ToolExecutionResult result = ToolExecutionResult.builder().build();

        // When
        result.setDurationMs(0);
        assertEquals(0, result.getDurationMs());

        result.setDurationMs(1000);
        assertEquals(1000, result.getDurationMs());
    }

    @Test
    @DisplayName("should_build_pending_approval_result")
    void pendingApproval_result_shouldHaveCorrectFields() {
        // When
        ToolExecutionResult result = ToolExecutionResult.builder()
                .callId("call_pending")
                .status("pending_approval")
                .approvalId("approval_123")
                .riskLevel("high")
                .build();

        // Then
        assertEquals("pending_approval", result.getStatus());
        assertNotNull(result.getApprovalId());
        assertEquals("high", result.getRiskLevel());
    }
}
