package com.platform.toolbus.registry;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 工具注册表
 */
@Slf4j
@Component
public class ToolRegistry {

    private final Map<String, ToolDefinition> tools = new ConcurrentHashMap<>();

    public ToolRegistry() {
        // 注册 Mock 工具
        registerMockTools();
    }

    private void registerMockTools() {
        // 查询订单状态 - 低风险只读工具
        register(ToolDefinition.builder()
                .name("query_order_status")
                .version("1.0")
                .category("query")
                .description("查询订单状态")
                .riskLevel("low")
                .requiresApproval(false)
                .inputSchema("""
                    {
                        "type": "object",
                        "properties": {
                            "order_id": {"type": "string", "description": "订单 ID"}
                        },
                        "required": ["order_id"]
                    }
                    """)
                .build());

        // 获取用户信息 - 低风险只读工具
        register(ToolDefinition.builder()
                .name("get_user_info")
                .version("1.0")
                .category("query")
                .description("获取用户基本信息")
                .riskLevel("low")
                .requiresApproval(false)
                .inputSchema("""
                    {
                        "type": "object",
                        "properties": {
                            "user_id": {"type": "string", "description": "用户 ID"}
                        },
                        "required": ["user_id"]
                    }
                    """)
                .build());

        // 模拟写操作 - 高风险工具
        register(ToolDefinition.builder()
                .name("mock_write_operation")
                .version("1.0")
                .category("write")
                .description("模拟写操作（高风险）")
                .riskLevel("high")
                .requiresApproval(true)
                .approvalCondition("{\"amount\": {\"$gt\": 10000}}")
                .inputSchema("""
                    {
                        "type": "object",
                        "properties": {
                            "operation": {"type": "string", "description": "操作类型"},
                            "amount": {"type": "number", "description": "金额"}
                        },
                        "required": ["operation"]
                    }
                    """)
                .build());

        log.info("Registered {} mock tools", tools.size());
    }

    public void register(ToolDefinition tool) {
        String key = tool.getName() + "_v" + tool.getVersion();
        tools.put(key, tool);
        log.debug("Registered tool: {}", key);
    }

    public Optional<ToolDefinition> get(String name, String version) {
        String key = name + "_v" + (version != null ? version : "1.0");
        return Optional.ofNullable(tools.get(key))
                .or(() -> Optional.ofNullable(tools.get(name + "_vlatest")));
    }

    public Optional<ToolDefinition> get(String name) {
        return get(name, "1.0");
    }

    public List<ToolDefinition> listAll() {
        return new ArrayList<>(tools.values());
    }

    public List<ToolDefinition> listByCategory(String category) {
        return tools.values().stream()
                .filter(t -> t.getCategory().equals(category))
                .toList();
    }
}
