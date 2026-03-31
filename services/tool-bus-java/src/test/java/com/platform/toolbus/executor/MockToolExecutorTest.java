package com.platform.toolbus.executor;

import com.platform.toolbus.registry.ToolRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

/**
 * MockToolExecutor unit tests
 *
 * Six-dimensional quality check:
 * T1 - Naming: Given/When/Then pattern used
 * T2 - Fragility: Asserts behavior, not implementation
 * T3 - Repetition: No parameterized tests needed (distinct scenarios)
 * T4 - Mock abuse: Only external dependency (ToolRegistry) is mocked
 * T5 - Coverage illusion: All assertions are meaningful
 * T6 - Architecture: Unit test level is appropriate
 */
@ExtendWith(MockitoExtension.class)
class MockToolExecutorTest {

    @Mock
    private ToolRegistry toolRegistry;

    private MockToolExecutor executor;

    @BeforeEach
    void setUp() {
        executor = new MockToolExecutor(toolRegistry);
    }

    // ==================== Success scenarios ====================

    @Test
    @DisplayName("should_return_success_when_query_order_status_tool_executed")
    void execute_queryOrderStatus_returnsSuccess() {
        // Given
        String toolName = "query_order_status";
        String version = "1.0";
        String argumentsJson = "{\"order_id\": \"ORD-12345\"}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .version(version)
                .category("query")
                .description("Query order status")
                .riskLevel("low")
                .build();

        when(toolRegistry.get(toolName, version)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, version, argumentsJson);

        // Then
        assertEquals("success", result.getStatus());
        assertNotNull(result.getCallId());
        assertNotNull(result.getResultJson());
        assertTrue(result.getDurationMs() >= 0);
        assertFalse(result.isWasCached());
        assertNull(result.getErrorCode());
        assertNull(result.getErrorMessage());
    }

    @Test
    @DisplayName("should_return_user_info_when_get_user_info_tool_executed")
    void execute_getUserInfo_returnsSuccess() {
        // Given
        String toolName = "get_user_info";
        String argumentsJson = "{\"user_id\": \"USR-001\"}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .category("query")
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, argumentsJson);

        // Then
        assertEquals("success", result.getStatus());
        assertTrue(result.getResultJson().contains("user_id"));
        assertTrue(result.getResultJson().contains("USR-001"));
    }

    @Test
    @DisplayName("should_return_transaction_id_when_write_operation_executed")
    void execute_writeOperation_returnsSuccessWithTransactionId() {
        // Given
        String toolName = "mock_write_operation";
        String argumentsJson = "{\"operation\": \"credit\", \"amount\": 500}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .category("write")
                .riskLevel("high")
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, argumentsJson);

        // Then
        assertEquals("success", result.getStatus());
        assertTrue(result.getResultJson().contains("transaction_id"));
        assertTrue(result.getResultJson().contains("MOCK-"));
    }

    // ==================== Tool not found scenarios ====================

    @Test
    @DisplayName("should_return_failed_when_tool_not_found")
    void execute_toolNotFound_returnsFailed() {
        // Given
        String toolName = "non_existent_tool";
        when(toolRegistry.get(toolName, null)).thenReturn(Optional.empty());

        // When
        ToolExecutionResult result = executor.execute(toolName, null, "{}");

        // Then
        assertEquals("failed", result.getStatus());
        assertEquals("ERR_AGENT_TOOL_NOT_FOUND", result.getErrorCode());
        assertTrue(result.getErrorMessage().contains("Tool not found"));
        assertNull(result.getResultJson());
    }

    @Test
    @DisplayName("should_return_failed_when_tool_not_found_with_version")
    void execute_toolNotFoundWithVersion_returnsFailed() {
        // Given
        String toolName = "some_tool";
        String version = "2.0";
        when(toolRegistry.get(toolName, version)).thenReturn(Optional.empty());

        // When
        ToolExecutionResult result = executor.execute(toolName, version, "{}");

        // Then
        assertEquals("failed", result.getStatus());
        assertEquals("ERR_AGENT_TOOL_NOT_FOUND", result.getErrorCode());
    }

    // ==================== Invalid arguments scenarios ====================

    @Test
    @DisplayName("should_return_failed_when_arguments_json_invalid")
    void execute_invalidJsonArguments_returnsFailed() {
        // Given
        String toolName = "query_order_status";
        String invalidJson = "{invalid json}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, invalidJson);

        // Then
        assertEquals("failed", result.getStatus());
        assertEquals("ERR_TOOL_EXECUTION_FAILED", result.getErrorCode());
        assertNotNull(result.getErrorMessage());
    }

    @Test
    @DisplayName("should_return_failed_when_arguments_json_is_null")
    void execute_nullArgumentsJson_returnsFailed() {
        // Given
        String toolName = "query_order_status";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, null);

        // Then
        assertEquals("failed", result.getStatus());
        assertEquals("ERR_TOOL_EXECUTION_FAILED", result.getErrorCode());
    }

    // ==================== Edge cases ====================

    @Test
    @DisplayName("should_handle_empty_arguments_gracefully")
    void execute_emptyArguments_returnsSuccess() {
        // Given
        String toolName = "query_order_status";
        String emptyJson = "{}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, emptyJson);

        // Then
        assertEquals("success", result.getStatus());
    }

    @Test
    @DisplayName("should_generate_unique_call_id_for_each_execution")
    void execute_generatesUniqueCallId() {
        // Given
        String toolName = "query_order_status";
        String argumentsJson = "{}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result1 = executor.execute(toolName, null, argumentsJson);
        ToolExecutionResult result2 = executor.execute(toolName, null, argumentsJson);

        // Then
        assertNotEquals(result1.getCallId(), result2.getCallId());
    }

    @Test
    @DisplayName("should_return_unknown_tool_message_for_unimplemented_tool")
    void execute_unknownTool_returnsUnknownToolMessage() {
        // Given
        String toolName = "new_tool_not_implemented";
        String argumentsJson = "{}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, argumentsJson);

        // Then
        assertEquals("success", result.getStatus());
        assertTrue(result.getResultJson().contains("Unknown tool"));
    }

    @Test
    @DisplayName("should_record_execution_duration")
    void execute_recordsDuration() throws InterruptedException {
        // Given
        String toolName = "query_order_status";
        String argumentsJson = "{}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, argumentsJson);

        // Then
        assertTrue(result.getDurationMs() >= 0);
    }

    @Test
    @DisplayName("should_handle_complex_nested_json_arguments")
    void execute_complexJsonArguments_returnsSuccess() {
        // Given
        String toolName = "query_order_status";
        String complexJson = "{\"order_id\": \"ORD-123\", \"metadata\": {\"source\": \"web\", \"tags\": [\"urgent\", \"vip\"]}}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, complexJson);

        // Then
        assertEquals("success", result.getStatus());
    }

    @Test
    @DisplayName("should_handle_special_characters_in_arguments")
    void execute_specialCharactersInArguments_returnsSuccess() {
        // Given
        String toolName = "query_order_status";
        String specialCharsJson = "{\"order_id\": \"ORD-\\\"test\\\"\", \"note\": \"a\\nb\\tc\"}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, specialCharsJson);

        // Then
        assertEquals("success", result.getStatus());
    }

    @Test
    @DisplayName("should_return_mock_success_status_for_write_operation")
    void execute_writeOperation_returnsMockSuccessStatus() {
        // Given
        String toolName = "mock_write_operation";
        String argumentsJson = "{\"operation\": \"debit\", \"amount\": 1000}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, argumentsJson);

        // Then
        assertTrue(result.getResultJson().contains("mock_success"));
    }

    @Test
    @DisplayName("should_handle_numeric_amount_values")
    void execute_numericAmount_returnsCorrectValue() {
        // Given
        String toolName = "mock_write_operation";
        String argumentsJson = "{\"operation\": \"test\", \"amount\": 123.45}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, argumentsJson);

        // Then
        assertTrue(result.getResultJson().contains("123.45"));
    }

    @Test
    @DisplayName("should_use_default_values_when_arguments_missing")
    void execute_missingArguments_usesDefaults() {
        // Given
        String toolName = "query_order_status";
        String emptyJson = "{}";

        var toolDef = com.platform.toolbus.registry.ToolDefinition.builder()
                .name(toolName)
                .build();

        when(toolRegistry.get(toolName, null)).thenReturn(Optional.of(toolDef));

        // When
        ToolExecutionResult result = executor.execute(toolName, null, emptyJson);

        // Then
        assertEquals("success", result.getStatus());
        assertTrue(result.getResultJson().contains("order_id"));
    }
}
