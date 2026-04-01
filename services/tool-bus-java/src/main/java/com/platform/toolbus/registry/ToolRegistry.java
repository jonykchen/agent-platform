package com.platform.toolbus.registry;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 工具注册表
 *
 * 【设计模式】注册表模式 (Registry Pattern)
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * 工具注册表集中管理所有可用工具的定义：
 * - 工具名称、版本、类别
 * - 输入参数 Schema（JSON Schema）
 * - 风险等级、是否需要审批
 *
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          工具注册生命周期                                    │
 * │                                                                             │
 * │   应用启动                                                                   │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  ToolRegistry 构造函数                                             │    │
 * │   │  - registerMockTools() 注册 Mock 工具                             │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  ConcurrentHashMap<String, ToolDefinition>                        │    │
 * │   │  - 线程安全的工具存储                                             │    │
 * │   │  - Key: toolName_vversion                                        │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │       │                                                                     │
 * │       ├─── 查询: get(toolName)                                             │
 * │       │                                                                     │
 * │       └─── 列表: listAll(), listByCategory()                               │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *
 * 【技术选型】工具存储方案
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ ConcurrentHashMap  │ • 线程安全                  │ • 进程重启丢失              │
 * │ (当前选择)         │ • 性能最优                  │ • 不支持动态更新            │
 * │                    │ • 无外部依赖                │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 数据库存储         │ • 持久化                    │ • 查询有延迟                │
 * │                    │ • 支持动态更新              │ • 需缓存策略                │
 * │                    │ • 审计追踪                  │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Redis 缓存         │ • 分布式共享                │ • 依赖外部服务              │
 * │                    │ • 性能好                    │ • 序列化开销                │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【选择 ConcurrentHashMap 的原因】
 * 1. 开发阶段，工具定义相对静态
 * 2. 性能最优，无网络开销
 * 3. 生产环境可扩展为数据库 + 缓存模式
 *
 * 【版本管理】
 * - 工具可多版本共存（v1.0, v2.0）
 * - 默认获取最新版本
 * - Key 格式: toolName_vversion
 *
 * 【后续优化方向】
 * - 从数据库加载工具定义
 * - 支持热更新（无需重启）
 * - 添加工具启用/禁用状态
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
