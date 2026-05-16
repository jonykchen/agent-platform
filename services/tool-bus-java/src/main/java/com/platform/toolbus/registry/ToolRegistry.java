package com.platform.toolbus.registry;

import com.platform.toolbus.entity.ToolDefinitionEntity;
import com.platform.toolbus.repository.ToolDefinitionRepository;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 工具注册表
 *
 * <p>集中管理所有可用工具的定义：
 * <ul>
 *   <li>工具名称、版本、类别</li>
 *   <li>输入参数 Schema（JSON Schema）</li>
 *   <li>风险等级、是否需要审批</li>
 * </ul>
 *
 * <h2>设计模式</h2>
 * <p>注册表模式 (Registry Pattern) - 提供全局访问点，支持动态注册和查询。
 *
 * <h2>数据加载流程</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────┐
 * │                        工具注册生命周期                              │
 * │                                                                     │
 * │   应用启动                                                           │
 * │       │                                                             │
 * │       ▼                                                             │
 * │   ┌─────────────────────────────────────────────────────────────┐  │
 * │   │  @PostConstruct                                              │  │
 * │   │  loadFromDatabase() → 从数据库加载启用的工具                   │  │
 * │   └─────────────────────────────────────────────────────────────┘  │
 * │       │                                                             │
 * │       ▼                                                             │
 * │   ┌─────────────────────────────────────────────────────────────┐  │
 * │   │  ConcurrentHashMap<String, ToolDefinition>                  │  │
 * │   │  - 线程安全的工具存储                                         │  │
 * │   │  - Key: toolName_vversion                                   │  │
 * │   └─────────────────────────────────────────────────────────────┘  │
 * │       │                                                             │
 * │       ├─── 查询: get(toolName)                                     │
 * │       └─── 列表: listAll(), listByCategory()                       │
 * │                                                                     │
 * └─────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>版本管理</h2>
 * <ul>
 *   <li>工具可多版本共存（v1.0, v2.0）</li>
 *   <li>默认获取版本 1.0</li>
 *   <li>Key 格式: {@code toolName_vversion}</li>
 * </ul>
 *
 * <h2>动态注册</h2>
 * <p>支持运行时动态注册新工具，通过 {@link #loadFromDatabase(ToolDefinitionRepository)}
 * 从数据库重新加载，实现热更新。
 *
 * @see ToolDefinition
 * @see ToolDefinitionEntity
 * @see com.platform.toolbus.repository.ToolDefinitionRepository
 */
@Slf4j
@Component
public class ToolRegistry {

    /**
     * 工具定义 Repository（延迟注入）
     */
    private ToolDefinitionRepository repository;

    /**
     * 工具存储映射
     * <p>Key 格式: {@code toolName_vversion}
     */
    private final Map<String, ToolDefinition> tools = new ConcurrentHashMap<>();

    /**
     * 默认构造函数
     */
    public ToolRegistry() {
        // 空构造，等待 Repository 注入后通过 @PostConstruct 加载
    }

    /**
     * 设置 Repository（用于依赖注入）
     *
     * @param repository 工具定义 Repository
     */
    public void setRepository(ToolDefinitionRepository repository) {
        this.repository = repository;
    }

    /**
     * 初始化方法：从数据库加载工具定义
     *
     * <p>在 Spring 完成依赖注入后自动执行。
     * 如果数据库中没有工具定义，则注册默认工具集。
     */
    @PostConstruct
    public void init() {
        if (repository != null) {
            loadFromDatabase(repository);
        }
        // 如果没有数据，注册默认工具作为兜底
        if (tools.isEmpty()) {
            registerDefaultTools();
        }
    }

    /**
     * 注册默认工具（兜底方案）
     *
     * <p>当数据库中没有工具定义时，注册一组默认工具，
     * 确保服务可用。这主要用于开发环境和首次启动场景。
     */
    private void registerDefaultTools() {
        log.warn("No tools found in database, registering default tools...");

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

        log.info("Registered {} default tools", tools.size());
    }

    /**
     * 从数据库加载工具定义
     *
     * <p>加载所有启用的工具定义，转换为内存对象并注册到内存映射中。
     * 该方法支持热更新，可在运行时调用以刷新工具定义。
     *
     * <h3>使用场景</h3>
     * <ul>
     *   <li>应用启动时自动加载（通过 @PostConstruct）</li>
     *   <li>管理员更新工具后手动刷新</li>
     *   <li>定时任务同步数据库变更</li>
     * </ul>
     *
     * @param repository 工具定义 Repository
     */
    public void loadFromDatabase(ToolDefinitionRepository repository) {
        log.info("Loading tool definitions from database...");

        List<ToolDefinitionEntity> entities = repository.findByEnabledTrue();
        int loadedCount = 0;

        for (ToolDefinitionEntity entity : entities) {
            ToolDefinition definition = convertToDefinition(entity);
            register(definition);
            loadedCount++;
        }

        log.info("Loaded {} tool definitions from database", loadedCount);
    }

    /**
     * 将 JPA 实体转换为内存对象
     *
     * @param entity JPA 实体
     * @return 工具定义内存对象
     */
    private ToolDefinition convertToDefinition(ToolDefinitionEntity entity) {
        return ToolDefinition.builder()
                .name(entity.getName())
                .version(entity.getVersion())
                .category(entity.getCategory())
                .description(entity.getDescription())
                .inputSchema(entity.getInputSchema())
                .outputSchema(entity.getOutputSchema())
                .riskLevel(entity.getRiskLevel())
                .requiresApproval(entity.getRequiresApproval() != null && entity.getRequiresApproval())
                .approvalCondition(entity.getApprovalCondition())
                .build();
    }

    /**
     * 注册工具定义
     *
     * <p>将工具定义添加到内存映射中，Key 格式为 {@code toolName_vversion}。
     * 如果已存在同名同版本的工具，将被覆盖。
     *
     * @param tool 工具定义
     */
    public void register(ToolDefinition tool) {
        String key = tool.getName() + "_v" + tool.getVersion();
        tools.put(key, tool);
        log.debug("Registered tool: {}", key);
    }

    /**
     * 取消注册工具
     *
     * <p>从内存映射中移除指定名称和版本的工具。
     *
     * @param name    工具名称
     * @param version 版本号（可选，默认 1.0）
     * @return 是否成功移除
     */
    public boolean unregister(String name, String version) {
        String key = name + "_v" + (version != null ? version : "1.0");
        ToolDefinition removed = tools.remove(key);
        if (removed != null) {
            log.debug("Unregistered tool: {}", key);
            return true;
        }
        return false;
    }

    /**
     * 取消注册工具（默认版本）
     *
     * @param name 工具名称
     * @return 是否成功移除
     */
    public boolean unregister(String name) {
        return unregister(name, "1.0");
    }

    /**
     * 清空所有工具定义
     *
     * <p>用于重新加载前的清理操作。
     */
    public void clear() {
        tools.clear();
        log.debug("All tools cleared from registry");
    }

    /**
     * 刷新工具定义（重新从数据库加载）
     *
     * <p>清空当前内存映射，然后从数据库重新加载所有启用的工具。
     *
     * @return 加载的工具数量
     */
    public int refresh() {
        if (repository == null) {
            log.warn("Repository not set, cannot refresh from database");
            return 0;
        }
        clear();
        loadFromDatabase(repository);
        if (tools.isEmpty()) {
            registerDefaultTools();
        }
        return tools.size();
    }

    /**
     * 按名称和版本获取工具定义
     *
     * <p>如果指定版本不存在，尝试查找 {@code latest} 版本。
     *
     * @param name    工具名称
     * @param version 版本号（可选）
     * @return 工具定义（可选）
     */
    public Optional<ToolDefinition> get(String name, String version) {
        String key = name + "_v" + (version != null ? version : "1.0");
        return Optional.ofNullable(tools.get(key))
                .or(() -> Optional.ofNullable(tools.get(name + "_vlatest")));
    }

    /**
     * 按名称获取工具定义（默认版本）
     *
     * @param name 工具名称
     * @return 工具定义（可选）
     */
    public Optional<ToolDefinition> get(String name) {
        return get(name, "1.0");
    }

    /**
     * 获取所有工具定义
     *
     * @return 所有工具定义列表
     */
    public List<ToolDefinition> listAll() {
        return new ArrayList<>(tools.values());
    }

    /**
     * 按类别获取工具定义
     *
     * @param category 类别（query/write/external）
     * @return 该类别的工具定义列表
     */
    public List<ToolDefinition> listByCategory(String category) {
        return tools.values().stream()
                .filter(t -> t.getCategory().equals(category))
                .toList();
    }

    /**
     * 获取工具总数
     *
     * @return 当前注册的工具数量
     */
    public int size() {
        return tools.size();
    }

    /**
     * 检查工具是否存在
     *
     * @param name    工具名称
     * @param version 版本号（可选）
     * @return 是否存在
     */
    public boolean exists(String name, String version) {
        return get(name, version).isPresent();
    }

    /**
     * 检查工具是否存在（默认版本）
     *
     * @param name 工具名称
     * @return 是否存在
     */
    public boolean exists(String name) {
        return get(name).isPresent();
    }
}
