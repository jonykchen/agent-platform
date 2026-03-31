package com.platform.toolbus.permission;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * ToolPermissionDeniedException unit tests
 */
class ToolPermissionDeniedExceptionTest {

    @Test
    @DisplayName("should_create_exception_with_error_code_and_message")
    void constructor_withCodeAndMessage_createsException() {
        // Given
        String errorCode = "TEST_ERROR";
        String message = "Test error message";

        // When
        ToolPermissionDeniedException exception = new ToolPermissionDeniedException(errorCode, message);

        // Then
        assertEquals(errorCode, exception.getErrorCode());
        assertEquals(message, exception.getMessage());
        assertNull(exception.getToolName());
        assertNull(exception.getTenantId());
    }

    @Test
    @DisplayName("should_create_exception_with_all_fields")
    void constructor_withAllFields_createsException() {
        // Given
        String errorCode = "ACCESS_DENIED";
        String message = "Access denied";
        String toolName = "delete_user";
        String tenantId = "tenant_001";

        // When
        ToolPermissionDeniedException exception = new ToolPermissionDeniedException(
                errorCode, message, toolName, tenantId);

        // Then
        assertEquals(errorCode, exception.getErrorCode());
        assertEquals(message, exception.getMessage());
        assertEquals(toolName, exception.getToolName());
        assertEquals(tenantId, exception.getTenantId());
    }

    @Test
    @DisplayName("should_create_roleNotAllowed_exception")
    void roleNotAllowed_createsCorrectException() {
        // Given
        String toolName = "admin_tool";
        String roleName = "guest";

        // When
        ToolPermissionDeniedException exception = ToolPermissionDeniedException.roleNotAllowed(toolName, roleName);

        // Then
        assertEquals("TOOL_NOT_ALLOWED", exception.getErrorCode());
        assertTrue(exception.getMessage().contains("guest"));
        assertTrue(exception.getMessage().contains("admin_tool"));
        assertEquals(toolName, exception.getToolName());
    }

    @Test
    @DisplayName("should_create_toolNotEnabledForTenant_exception")
    void toolNotEnabledForTenant_createsCorrectException() {
        // Given
        String toolName = "premium_feature";
        String tenantId = "tenant_free";

        // When
        ToolPermissionDeniedException exception = ToolPermissionDeniedException.toolNotEnabledForTenant(toolName, tenantId);

        // Then
        assertEquals("TOOL_NOT_ENABLED_FOR_TENANT", exception.getErrorCode());
        assertTrue(exception.getMessage().contains(tenantId));
        assertTrue(exception.getMessage().contains(toolName));
        assertEquals(toolName, exception.getToolName());
        assertEquals(tenantId, exception.getTenantId());
    }

    @Test
    @DisplayName("should_create_toolDisabled_exception_with_reason")
    void toolDisabled_createsCorrectException() {
        // Given
        String toolName = "payment_tool";
        String reason = "Payment module suspended due to compliance review";

        // When
        ToolPermissionDeniedException exception = ToolPermissionDeniedException.toolDisabled(toolName, reason);

        // Then
        assertEquals("TOOL_DISABLED", exception.getErrorCode());
        assertTrue(exception.getMessage().contains(toolName));
        assertTrue(exception.getMessage().contains(reason));
        assertEquals(toolName, exception.getToolName());
    }

    @Test
    @DisplayName("should_create_abacConditionFailed_exception")
    void abacConditionFailed_createsCorrectException() {
        // Given
        String condition = "max_amount";

        // When
        ToolPermissionDeniedException exception = ToolPermissionDeniedException.abacConditionFailed(condition);

        // Then
        assertEquals("ABAC_CONDITION_FAILED", exception.getErrorCode());
        assertTrue(exception.getMessage().contains(condition));
    }

    @Test
    @DisplayName("should_create_quotaExceeded_exception")
    void quotaExceeded_createsCorrectException() {
        // Given
        String toolName = "api_call";
        String quotaType = "daily";

        // When
        ToolPermissionDeniedException exception = ToolPermissionDeniedException.quotaExceeded(toolName, quotaType);

        // Then
        assertEquals("QUOTA_EXCEEDED", exception.getErrorCode());
        assertTrue(exception.getMessage().contains(toolName));
        assertTrue(exception.getMessage().contains(quotaType));
        assertEquals(toolName, exception.getToolName());
    }

    @Test
    @DisplayName("should_be_runtime_exception")
    void exception_isRuntimeException() {
        // Given
        ToolPermissionDeniedException exception = ToolPermissionDeniedException.roleNotAllowed("tool", "role");

        // Then
        assertTrue(exception instanceof RuntimeException);
    }

    @Test
    @DisplayName("should_preserve_error_code_for_all_factory_methods")
    void factoryMethods_preserveErrorCode() {
        assertEquals("TOOL_NOT_ALLOWED",
                ToolPermissionDeniedException.roleNotAllowed("tool", "role").getErrorCode());
        assertEquals("TOOL_NOT_ENABLED_FOR_TENANT",
                ToolPermissionDeniedException.toolNotEnabledForTenant("tool", "tenant").getErrorCode());
        assertEquals("TOOL_DISABLED",
                ToolPermissionDeniedException.toolDisabled("tool", "reason").getErrorCode());
        assertEquals("ABAC_CONDITION_FAILED",
                ToolPermissionDeniedException.abacConditionFailed("condition").getErrorCode());
        assertEquals("QUOTA_EXCEEDED",
                ToolPermissionDeniedException.quotaExceeded("tool", "type").getErrorCode());
    }
}
