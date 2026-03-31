package com.platform.toolbus.executor;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * ToolExecutionContext unit tests
 */
class ToolExecutionContextTest {

    @Test
    @DisplayName("should_build_context_with_all_fields")
    void builder_shouldCreateCompleteContext() {
        // When
        ToolExecutionContext ctx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .userId("user_123")
                .roleName("admin")
                .requestId("req_abc")
                .sessionId("session_xyz")
                .runId("run_789")
                .build();

        // Then
        assertEquals("tenant_001", ctx.getTenantId());
        assertEquals("user_123", ctx.getUserId());
        assertEquals("admin", ctx.getRoleName());
        assertEquals("req_abc", ctx.getRequestId());
        assertEquals("session_xyz", ctx.getSessionId());
        assertEquals("run_789", ctx.getRunId());
    }

    @Test
    @DisplayName("should_create_default_context_for_testing")
    void defaultContext_shouldCreateTestContext() {
        // When
        ToolExecutionContext ctx = ToolExecutionContext.defaultContext();

        // Then
        assertEquals("default", ctx.getTenantId());
        assertEquals("test_user", ctx.getUserId());
        assertEquals("admin", ctx.getRoleName());
        assertEquals("req_test", ctx.getRequestId());
        assertNull(ctx.getSessionId());
        assertNull(ctx.getRunId());
    }

    @Test
    @DisplayName("should_allow_null_optional_fields")
    void builder_withNullFields_shouldSucceed() {
        // When
        ToolExecutionContext ctx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .userId("user_123")
                .roleName("user")
                .build();

        // Then
        assertNull(ctx.getRequestId());
        assertNull(ctx.getSessionId());
        assertNull(ctx.getRunId());
    }

    @Test
    @DisplayName("should_allow_modification_via_setters")
    void setters_shouldModifyFields() {
        // Given
        ToolExecutionContext ctx = ToolExecutionContext.builder().build();

        // When
        ctx.setTenantId("new_tenant");
        ctx.setUserId("new_user");
        ctx.setRoleName("new_role");
        ctx.setRequestId("new_request");
        ctx.setSessionId("new_session");
        ctx.setRunId("new_run");

        // Then
        assertEquals("new_tenant", ctx.getTenantId());
        assertEquals("new_user", ctx.getUserId());
        assertEquals("new_role", ctx.getRoleName());
        assertEquals("new_request", ctx.getRequestId());
        assertEquals("new_session", ctx.getSessionId());
        assertEquals("new_run", ctx.getRunId());
    }

    @Test
    @DisplayName("should_build_empty_context")
    void emptyBuilder_shouldCreateEmptyContext() {
        // When
        ToolExecutionContext ctx = ToolExecutionContext.builder().build();

        // Then
        assertNull(ctx.getTenantId());
        assertNull(ctx.getUserId());
        assertNull(ctx.getRoleName());
    }

    @Test
    @DisplayName("should_handle_equality_correctly")
    void equality_shouldWorkCorrectly() {
        // Given
        ToolExecutionContext ctx1 = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .userId("user_001")
                .build();
        ToolExecutionContext ctx2 = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .userId("user_001")
                .build();
        ToolExecutionContext ctx3 = ToolExecutionContext.builder()
                .tenantId("tenant_002")
                .userId("user_001")
                .build();

        // When & Then
        assertEquals(ctx1, ctx2);
        assertNotEquals(ctx1, ctx3);
        assertEquals(ctx1.hashCode(), ctx2.hashCode());
    }

    @Test
    @DisplayName("should_generate_string_representation")
    void toString_shouldContainFields() {
        // Given
        ToolExecutionContext ctx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("admin")
                .build();

        // When
        String str = ctx.toString();

        // Then
        assertTrue(str.contains("tenant_001"));
        assertTrue(str.contains("admin"));
    }

    @Test
    @DisplayName("should_support_various_role_names")
    void roleName_shouldSupportVariousValues() {
        // Given
        ToolExecutionContext ctx = ToolExecutionContext.builder().build();
        String[] roles = {"admin", "user", "viewer", "finance", "hr", "operator"};

        for (String role : roles) {
            // When
            ctx.setRoleName(role);

            // Then
            assertEquals(role, ctx.getRoleName());
        }
    }
}
