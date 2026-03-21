package com.platform.toolbus.registry;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 工具定义测试
 */
class ToolDefinitionTest {

    @Test
    void toolDefinition_shouldBuildCorrectly() {
        ToolDefinition tool = ToolDefinition.builder()
                .name("test_tool")
                .version("2.0")
                .category("write")
                .description("Test tool description")
                .inputSchema("{\"type\": \"object\"}")
                .outputSchema("{\"type\": \"string\"}")
                .riskLevel("medium")
                .requiresApproval(true)
                .approvalCondition("{\"amount\": {\"$gt\": 100}}")
                .build();

        assertEquals("test_tool", tool.getName());
        assertEquals("2.0", tool.getVersion());
        assertEquals("write", tool.getCategory());
        assertEquals("Test tool description", tool.getDescription());
        assertEquals("{\"type\": \"object\"}", tool.getInputSchema());
        assertEquals("{\"type\": \"string\"}", tool.getOutputSchema());
        assertEquals("medium", tool.getRiskLevel());
        assertTrue(tool.isRequiresApproval());
        assertEquals("{\"amount\": {\"$gt\": 100}}", tool.getApprovalCondition());
    }

    @Test
    void toolDefinition_shouldHaveDefaultValues() {
        ToolDefinition tool = ToolDefinition.builder()
                .name("minimal_tool")
                .build();

        assertEquals("minimal_tool", tool.getName());
        assertNull(tool.getVersion());
        assertNull(tool.getCategory());
        assertFalse(tool.isRequiresApproval());
    }
}