package com.platform.toolbus.registry;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 工具注册表测试
 */
class ToolRegistryTest {

    private ToolRegistry toolRegistry;

    @BeforeEach
    void setUp() {
        toolRegistry = new ToolRegistry();
    }

    @Test
    void get_shouldReturnToolByName() {
        Optional<ToolDefinition> tool = toolRegistry.get("query_order_status");

        assertTrue(tool.isPresent());
        assertEquals("query_order_status", tool.get().getName());
        assertEquals("query", tool.get().getCategory());
        assertEquals("low", tool.get().getRiskLevel());
    }

    @Test
    void get_shouldReturnEmptyForNonExistentTool() {
        Optional<ToolDefinition> tool = toolRegistry.get("non_existent_tool");

        assertFalse(tool.isPresent());
    }

    @Test
    void get_shouldReturnToolByVersion() {
        Optional<ToolDefinition> tool = toolRegistry.get("query_order_status", "1.0");

        assertTrue(tool.isPresent());
        assertEquals("query_order_status", tool.get().getName());
    }

    @Test
    void listAll_shouldReturnAllTools() {
        List<ToolDefinition> tools = toolRegistry.listAll();

        assertFalse(tools.isEmpty());
        assertTrue(tools.size() >= 3); // 至少有 3 个 mock 工具
    }

    @Test
    void listByCategory_shouldReturnQueryTools() {
        List<ToolDefinition> queryTools = toolRegistry.listByCategory("query");

        assertFalse(queryTools.isEmpty());
        queryTools.forEach(tool -> assertEquals("query", tool.getCategory()));
    }

    @Test
    void register_shouldAddNewTool() {
        ToolDefinition newTool = ToolDefinition.builder()
                .name("test_tool")
                .version("1.0")
                .category("test")
                .description("Test tool")
                .riskLevel("low")
                .requiresApproval(false)
                .build();

        toolRegistry.register(newTool);

        Optional<ToolDefinition> found = toolRegistry.get("test_tool");
        assertTrue(found.isPresent());
        assertEquals("test_tool", found.get().getName());
    }

    @Test
    void toolDefinition_shouldHaveCorrectRiskLevels() {
        // 查询工具应该是低风险
        Optional<ToolDefinition> queryTool = toolRegistry.get("query_order_status");
        assertTrue(queryTool.isPresent());
        assertEquals("low", queryTool.get().getRiskLevel());
        assertFalse(queryTool.get().isRequiresApproval());

        // 写操作工具应该是高风险
        Optional<ToolDefinition> writeTool = toolRegistry.get("mock_write_operation");
        assertTrue(writeTool.isPresent());
        assertEquals("high", writeTool.get().getRiskLevel());
        assertTrue(writeTool.get().isRequiresApproval());
    }

    @Test
    void toolDefinition_shouldHaveInputSchema() {
        Optional<ToolDefinition> tool = toolRegistry.get("query_order_status");

        assertTrue(tool.isPresent());
        assertNotNull(tool.get().getInputSchema());
        assertTrue(tool.get().getInputSchema().contains("order_id"));
    }
}