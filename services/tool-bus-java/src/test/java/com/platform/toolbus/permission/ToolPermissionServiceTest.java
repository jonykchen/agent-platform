package com.platform.toolbus.permission;

import com.platform.toolbus.executor.ToolExecutionContext;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.util.HashMap;
import java.util.Map;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * ToolPermissionService unit tests
 *
 * Six-dimensional quality check:
 * T1 - Naming: Given/When/Then pattern used
 * T2 - Fragility: Asserts behavior, not implementation
 * T3 - Repetition: Similar scenarios combined with descriptive names
 * T4 - Mock abuse: Only external dependencies mocked (repo, redis)
 * T5 - Coverage illusion: All assertions verify real business outcomes
 * T6 - Architecture: Unit test level is appropriate
 */
@ExtendWith(MockitoExtension.class)
class ToolPermissionServiceTest {

    @Mock
    private ToolPermissionRepository permissionRepo;

    @Mock
    private TenantToolConfigRepository configRepo;

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    private ToolPermissionService permissionService;

    @BeforeEach
    void setUp() {
        lenient().when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        permissionService = new ToolPermissionService(permissionRepo, configRepo, redisTemplate);
    }

    // ==================== Step 1: RBAC Check ====================

    @Test
    @DisplayName("should_throw_when_role_not_allowed_to_use_tool")
    void validatePermission_roleNotAllowed_throwsException() {
        // Given
        String toolName = "delete_user";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("viewer")
                .userId("user_001")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "viewer"))
                .thenReturn(Optional.empty());

        Map<String, Object> params = new HashMap<>();

        // When & Then
        ToolPermissionDeniedException exception = assertThrows(
                ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));

        assertEquals("TOOL_NOT_ALLOWED", exception.getErrorCode());
        verify(configRepo, never()).findByTenantIdAndToolName(anyString(), anyString());
    }

    @Test
    @DisplayName("should_pass_rbac_when_role_has_permission")
    void validatePermission_roleAllowed_passesRbac() {
        // Given
        String toolName = "query_order_status";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("admin")
                .userId("user_001")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .allowedActions("execute")
                .conditions(Map.of())
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(true)
                .dailyQuota(null)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();

        // When & Then - no exception thrown
        assertDoesNotThrow(() -> permissionService.validatePermission(toolName, userCtx, params));
    }

    // ==================== Step 2: Tenant Feature Toggle ====================

    @Test
    @DisplayName("should_throw_when_tenant_not_enabled_for_tool")
    void validatePermission_tenantNotEnabled_throwsException() {
        // Given
        String toolName = "payment_gateway";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_002")
                .roleName("admin")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_002", toolName))
                .thenReturn(Optional.empty());

        Map<String, Object> params = new HashMap<>();

        // When & Then
        ToolPermissionDeniedException exception = assertThrows(
                ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));

        assertEquals("TOOL_NOT_ENABLED_FOR_TENANT", exception.getErrorCode());
    }

    @Test
    @DisplayName("should_throw_when_tool_is_disabled_for_tenant")
    void validatePermission_toolDisabledForTenant_throwsException() {
        // Given
        String toolName = "payment_gateway";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("admin")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(false)
                .disabledReason("Payment module not activated")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();

        // When & Then
        ToolPermissionDeniedException exception = assertThrows(
                ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));

        assertEquals("TOOL_DISABLED", exception.getErrorCode());
        assertTrue(exception.getMessage().contains("Payment module not activated"));
    }

    // ==================== Step 3: ABAC Conditions ====================

    @Test
    @DisplayName("should_pass_when_abac_condition_satisfied")
    void validatePermission_abacConditionSatisfied_passes() {
        // Given
        String toolName = "process_payment";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("finance")
                .build();

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("max_amount", 10000);

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("finance")
                .conditions(conditions)
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(true)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "finance"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();
        params.put("amount", 5000); // Less than max_amount

        // When & Then
        assertDoesNotThrow(() -> permissionService.validatePermission(toolName, userCtx, params));
    }

    @Test
    @DisplayName("should_throw_when_abac_condition_not_satisfied")
    void validatePermission_abacConditionNotSatisfied_throwsException() {
        // Given
        String toolName = "process_payment";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("finance")
                .build();

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("max_amount", 10000);

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("finance")
                .conditions(conditions)
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(true)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "finance"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();
        params.put("amount", 15000); // Exceeds max_amount

        // When & Then
        ToolPermissionDeniedException exception = assertThrows(
                ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));

        assertEquals("ABAC_CONDITION_FAILED", exception.getErrorCode());
    }

    @Test
    @DisplayName("should_pass_when_no_abac_conditions_defined")
    void validatePermission_noAbacConditions_passes() {
        // Given
        String toolName = "simple_query";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("user")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("user")
                .conditions(null)
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(true)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "user"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();

        // When & Then
        assertDoesNotThrow(() -> permissionService.validatePermission(toolName, userCtx, params));
    }

    // ==================== Step 4: Daily Quota ====================

    @Test
    @DisplayName("should_pass_when_within_daily_quota")
    void validatePermission_withinQuota_passes() {
        // Given
        String toolName = "api_call";
        String tenantId = "tenant_001";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId(tenantId)
                .roleName("admin")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .conditions(Map.of())
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId(tenantId)
                .toolName(toolName)
                .isEnabled(true)
                .dailyQuota(100)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName(tenantId, toolName))
                .thenReturn(Optional.of(config));
        when(valueOperations.increment(anyString())).thenReturn(50L);

        Map<String, Object> params = new HashMap<>();

        // When & Then
        assertDoesNotThrow(() -> permissionService.validatePermission(toolName, userCtx, params));
    }

    @Test
    @DisplayName("should_throw_when_daily_quota_exceeded")
    void validatePermission_quotaExceeded_throwsException() {
        // Given
        String toolName = "api_call";
        String tenantId = "tenant_001";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId(tenantId)
                .roleName("admin")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .conditions(Map.of())
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId(tenantId)
                .toolName(toolName)
                .isEnabled(true)
                .dailyQuota(100)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName(tenantId, toolName))
                .thenReturn(Optional.of(config));
        when(valueOperations.increment(anyString())).thenReturn(101L);

        Map<String, Object> params = new HashMap<>();

        // When & Then
        ToolPermissionDeniedException exception = assertThrows(
                ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));

        assertEquals("QUOTA_EXCEEDED", exception.getErrorCode());
    }

    @Test
    @DisplayName("should_pass_when_quota_is_null_unlimited")
    void validatePermission_nullQuota_passes() {
        // Given
        String toolName = "unlimited_tool";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("admin")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .conditions(Map.of())
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(true)
                .dailyQuota(null) // Unlimited
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();

        // When & Then - no Redis call for quota check
        assertDoesNotThrow(() -> permissionService.validatePermission(toolName, userCtx, params));
        verify(valueOperations, never()).increment(anyString());
    }

    // ==================== requiresApproval ====================

    @Test
    @DisplayName("should_require_approval_when_condition_set")
    void requiresApproval_conditionSet_returnsTrue() {
        // Given
        String toolName = "delete_all_data";

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("requires_approval", true);

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .conditions(conditions)
                .build();

        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .roleName("admin")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));

        // When
        boolean result = permissionService.requiresApproval(toolName, userCtx);

        // Then
        assertTrue(result);
    }

    @Test
    @DisplayName("should_not_require_approval_when_condition_false")
    void requiresApproval_conditionFalse_returnsFalse() {
        // Given
        String toolName = "read_only_query";

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("requires_approval", false);

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("user")
                .conditions(conditions)
                .build();

        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .roleName("user")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "user"))
                .thenReturn(Optional.of(perm));

        // When
        boolean result = permissionService.requiresApproval(toolName, userCtx);

        // Then
        assertFalse(result);
    }

    @Test
    @DisplayName("should_require_approval_when_no_permission_found")
    void requiresApproval_noPermission_returnsTrue() {
        // Given
        String toolName = "restricted_tool";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .roleName("guest")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "guest"))
                .thenReturn(Optional.empty());

        // When
        boolean result = permissionService.requiresApproval(toolName, userCtx);

        // Then
        assertTrue(result); // Default to requiring approval
    }

    @Test
    @DisplayName("should_not_require_approval_when_no_conditions")
    void requiresApproval_noConditions_returnsFalse() {
        // Given
        String toolName = "simple_tool";

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("user")
                .conditions(null)
                .build();

        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .roleName("user")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "user"))
                .thenReturn(Optional.of(perm));

        // When
        boolean result = permissionService.requiresApproval(toolName, userCtx);

        // Then
        assertFalse(result);
    }

    // ==================== getMaxAmount ====================

    @Test
    @DisplayName("should_return_max_amount_when_defined")
    void getMaxAmount_amountDefined_returnsValue() {
        // Given
        String toolName = "payment_tool";

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("max_amount", 5000.0);

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("finance")
                .conditions(conditions)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "finance"))
                .thenReturn(Optional.of(perm));

        // When
        Double maxAmount = permissionService.getMaxAmount(toolName, "finance");

        // Then
        assertEquals(5000.0, maxAmount);
    }

    @Test
    @DisplayName("should_return_null_when_max_amount_not_defined")
    void getMaxAmount_notDefined_returnsNull() {
        // Given
        String toolName = "free_tool";

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("user")
                .conditions(Map.of())
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "user"))
                .thenReturn(Optional.of(perm));

        // When
        Double maxAmount = permissionService.getMaxAmount(toolName, "user");

        // Then
        assertNull(maxAmount);
    }

    @Test
    @DisplayName("should_return_null_when_permission_not_found")
    void getMaxAmount_permissionNotFound_returnsNull() {
        // Given
        when(permissionRepo.findByToolNameAndRoleName("unknown", "user"))
                .thenReturn(Optional.empty());

        // When
        Double maxAmount = permissionService.getMaxAmount("unknown", "user");

        // Then
        assertNull(maxAmount);
    }

    @Test
    @DisplayName("should_handle_integer_max_amount")
    void getMaxAmount_integerValue_returnsDouble() {
        // Given
        String toolName = "payment_tool";

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("max_amount", 10000); // Integer

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .conditions(conditions)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));

        // When
        Double maxAmount = permissionService.getMaxAmount(toolName, "admin");

        // Then
        assertEquals(10000.0, maxAmount);
    }

    // ==================== recordToolCall ====================

    @Test
    @DisplayName("should_record_successful_tool_call")
    void recordToolCall_success_recordsMetrics() {
        // Given
        String tenantId = "tenant_001";
        String toolName = "api_call";
        boolean success = true;
        long latencyMs = 150;

        // When
        permissionService.recordToolCall(tenantId, toolName, success, latencyMs);

        // Then
        verify(redisTemplate).opsForHash();
    }

    @Test
    @DisplayName("should_record_failed_tool_call")
    void recordToolCall_failure_recordsMetrics() {
        // Given
        String tenantId = "tenant_001";
        String toolName = "failing_tool";
        boolean success = false;
        long latencyMs = 300;

        // When
        permissionService.recordToolCall(tenantId, toolName, success, latencyMs);

        // Then
        verify(redisTemplate).opsForHash();
    }

    // ==================== ABAC List Conditions ====================

    @Test
    @DisplayName("should_pass_when_department_in_allowed_list")
    void validatePermission_departmentAllowed_passes() {
        // Given
        String toolName = "hr_tool";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("hr_manager")
                .build();

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("allowed_departments", java.util.List.of("hr", "finance", "it"));

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("hr_manager")
                .conditions(conditions)
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(true)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "hr_manager"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();
        params.put("department", "hr");

        // When & Then
        assertDoesNotThrow(() -> permissionService.validatePermission(toolName, userCtx, params));
    }

    @Test
    @DisplayName("should_throw_when_department_not_in_allowed_list")
    void validatePermission_departmentNotAllowed_throwsException() {
        // Given
        String toolName = "hr_tool";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("hr_manager")
                .build();

        Map<String, Object> conditions = new HashMap<>();
        conditions.put("allowed_departments", java.util.List.of("hr", "finance"));

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("hr_manager")
                .conditions(conditions)
                .build();

        TenantToolConfig config = TenantToolConfig.builder()
                .tenantId("tenant_001")
                .toolName(toolName)
                .isEnabled(true)
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "hr_manager"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName("tenant_001", toolName))
                .thenReturn(Optional.of(config));

        Map<String, Object> params = new HashMap<>();
        params.put("department", "marketing");

        // When & Then
        assertThrows(ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));
    }

    // ==================== Edge Cases ====================

    @Test
    @DisplayName("should_handle_empty_role_name")
    void validatePermission_emptyRoleName_throwsException() {
        // Given
        String toolName = "any_tool";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId("tenant_001")
                .roleName("")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, ""))
                .thenReturn(Optional.empty());

        Map<String, Object> params = new HashMap<>();

        // When & Then
        assertThrows(ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));
    }

    @Test
    @DisplayName("should_handle_null_tenant_id_in_context")
    void validatePermission_nullTenantId_throwsException() {
        // Given
        String toolName = "some_tool";
        ToolExecutionContext userCtx = ToolExecutionContext.builder()
                .tenantId(null)
                .roleName("admin")
                .build();

        ToolPermission perm = ToolPermission.builder()
                .toolName(toolName)
                .roleName("admin")
                .build();

        when(permissionRepo.findByToolNameAndRoleName(toolName, "admin"))
                .thenReturn(Optional.of(perm));
        when(configRepo.findByTenantIdAndToolName(null, toolName))
                .thenReturn(Optional.empty());

        Map<String, Object> params = new HashMap<>();

        // When & Then
        assertThrows(ToolPermissionDeniedException.class,
                () -> permissionService.validatePermission(toolName, userCtx, params));
    }
}
