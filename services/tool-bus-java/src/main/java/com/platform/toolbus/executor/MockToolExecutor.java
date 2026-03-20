package com.platform.toolbus.executor;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.toolbus.registry.ToolDefinition;
import com.platform.toolbus.registry.ToolRegistry;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;

/**
 * Mock 工具执行器
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class MockToolExecutor {

    private final ToolRegistry toolRegistry;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 执行工具调用
     */
    public ToolExecutionResult execute(String toolName, String version, String argumentsJson) {
        String callId = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        long startTime = System.currentTimeMillis();

        try {
            var toolOpt = toolRegistry.get(toolName, version);
            if (toolOpt.isEmpty()) {
                return ToolExecutionResult.builder()
                        .callId(callId)
                        .status("failed")
                        .errorCode("ERR_AGENT_TOOL_NOT_FOUND")
                        .errorMessage("Tool not found: " + toolName)
                        .build();
            }

            ToolDefinition tool = toolOpt.get();

            // 解析参数
            @SuppressWarnings("unchecked")
            Map<String, Object> args = objectMapper.readValue(argumentsJson, Map.class);

            // 执行 Mock 逻辑
            Object result = executeMockLogic(tool, args);

            long duration = System.currentTimeMillis() - startTime;

            return ToolExecutionResult.builder()
                    .callId(callId)
                    .status("success")
                    .resultJson(objectMapper.writeValueAsString(result))
                    .wasCached(false)
                    .durationMs((int) duration)
                    .build();

        } catch (Exception e) {
            log.error("Tool execution failed: {}", toolName, e);
            return ToolExecutionResult.builder()
                    .callId(callId)
                    .status("failed")
                    .errorCode("ERR_TOOL_EXECUTION_FAILED")
                    .errorMessage(e.getMessage())
                    .build();
        }
    }

    private Object executeMockLogic(ToolDefinition tool, Map<String, Object> args) {
        return switch (tool.getName()) {
            case "query_order_status" -> {
                String orderId = (String) args.getOrDefault("order_id", "unknown");
                yield Map.of(
                        "order_id", orderId,
                        "status", "delivered",
                        "amount", 299.00,
                        "created_at", "2026-05-01T10:00:00Z",
                        "updated_at", "2026-05-03T15:30:00Z"
                );
            }
            case "get_user_info" -> {
                String userId = (String) args.getOrDefault("user_id", "unknown");
                yield Map.of(
                        "user_id", userId,
                        "name", "张三",
                        "email", "zhang***@example.com",
                        "phone", "138****5678",
                        "level", "gold"
                );
            }
            case "mock_write_operation" -> {
                String operation = (String) args.getOrDefault("operation", "unknown");
                Number amount = (Number) args.getOrDefault("amount", 0);
                yield Map.of(
                        "operation", operation,
                        "amount", amount,
                        "status", "mock_success",
                        "transaction_id", "MOCK-" + UUID.randomUUID().toString().substring(0, 8)
                );
            }
            default -> Map.of("message", "Unknown tool");
        };
    }
}
