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
 *
 * 【设计模式】测试替身 (Test Double)
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * Mock 执行器用于开发测试阶段，模拟真实工具的行为：
 * - 无需连接真实外部系统（数据库、支付网关、物流系统）
 * - 响应可控，便于测试各种场景（成功、失败、审批需求）
 * - 性能基准：Mock 响应 < 50ms，真实工具可能数秒
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 测试替身类型       │ 适用场景                    │ 本项目应用                  │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Mock (当前使用)    │ • 返回预定义响应            │ 开发阶段，无真实系统        │
 * │                    │ • 无状态依赖                │                              │
 * │                    │ • 性能可控                  │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Stub               │ • 返回固定响应              │ 可用于单元测试              │
 * │                    │ • 简单场景                  │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Fake               │ • 有工作实现                │ 可用于集成测试              │
 * │                    │ • 如内存数据库              │ （如 InMemoryToolRegistry） │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Spy                │ • 记录调用信息              │ 可用于验证调用次数/参数     │
 * │                    │ • 部分 Mock                 │                              │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【Mock 数据生成原则】
 * 1. 数据真实性：订单状态、用户信息符合业务逻辑
 * 2. 敏感信息脱敏：手机号 138****5678，邮箱 zhang***@example.com
 * 3. 可测试性：返回数据包含唯一标识，便于追踪
 *
 * 【生产环境替换】
 * 开发完成后，MockToolExecutor 将被 RealToolExecutor 替换：
 * - RealToolExecutor 调用真实 gRPC 服务
 * - 通过 @Profile("dev") / @Profile("prod") 区分
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
