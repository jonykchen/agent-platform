package com.platform.toolbus.controller;

import com.platform.toolbus.entity.ToolDefinitionEntity;
import com.platform.toolbus.registry.ToolDefinition;
import com.platform.toolbus.registry.ToolRegistry;
import com.platform.toolbus.repository.ToolDefinitionRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * 工具管理控制器
 *
 * <p>提供工具动态注册、启用/禁用、查询等管理接口。
 *
 * <h2>接口列表</h2>
 * <table border="1">
 *   <tr><th>方法</th><th>路径</th><th>描述</th></tr>
 *   <tr><td>POST</td><td>/internal/tools/register</td><td>注册新工具</td></tr>
 *   <tr><td>POST</td><td>/internal/tools/{name}/enable</td><td>启用工具</td></tr>
 *   <tr><td>POST</td><td>/internal/tools/{name}/disable</td><td>禁用工具</td></tr>
 *   <tr><td>GET</td><td>/internal/tools</td><td>列出所有工具</td></tr>
 *   <tr><td>GET</td><td>/internal/tools/{name}</td><td>获取工具详情</td></tr>
 *   <tr><td>DELETE</td><td>/internal/tools/{name}</td><td>删除工具</td></tr>
 * </table>
 *
 * <h2>安全说明</h2>
 * <p>此控制器的所有接口都是内部接口（{@code /internal/*}），
 * 应通过网关进行访问控制，仅允许管理员或内部服务调用。
 *
 * @see ToolRegistry
 * @see ToolDefinitionEntity
 */
@Slf4j
@RestController
@RequestMapping("/internal/tools")
@RequiredArgsConstructor
public class ToolAdminController {

    private final ToolDefinitionRepository repository;
    private final ToolRegistry toolRegistry;

    /**
     * 注册新工具
     *
     * <p>将工具定义持久化到数据库，并注册到内存映射中。
     * 如果同名同版本的工具已存在，返回 409 Conflict。
     *
     * @param request 工具注册请求
     * @return 注册结果
     */
    @PostMapping("/register")
    public ResponseEntity<Map<String, Object>> registerTool(@RequestBody ToolRegistrationRequest request) {
        log.info("Registering tool: {} v{}", request.name(), request.version());

        // 检查是否已存在
        if (repository.existsByNameAndVersion(request.name(), request.version())) {
            log.warn("Tool already exists: {} v{}", request.name(), request.version());
            return ResponseEntity
                    .status(HttpStatus.CONFLICT)
                    .body(Map.of(
                            "error", "TOOL_ALREADY_EXISTS",
                            "message", String.format("Tool '%s' version '%s' already exists",
                                    request.name(), request.version())
                    ));
        }

        // 创建实体
        ToolDefinitionEntity entity = ToolDefinitionEntity.builder()
                .name(request.name())
                .version(request.version() != null ? request.version() : "1.0")
                .category(request.category())
                .description(request.description())
                .inputSchema(request.inputSchema())
                .outputSchema(request.outputSchema())
                .riskLevel(request.riskLevel() != null ? request.riskLevel() : "low")
                .requiresApproval(request.requiresApproval() != null ? request.requiresApproval() : false)
                .approvalCondition(request.approvalCondition())
                .enabled(true)
                .createdAt(Instant.now())
                .updatedAt(Instant.now())
                .build();

        // 持久化
        entity = repository.save(entity);
        log.info("Tool saved to database with id: {}", entity.getId());

        // 注册到内存
        ToolDefinition definition = convertToDefinition(entity);
        toolRegistry.register(definition);

        return ResponseEntity.ok(Map.of(
                "id", entity.getId().toString(),
                "name", entity.getName(),
                "version", entity.getVersion(),
                "message", "Tool registered successfully"
        ));
    }

    /**
     * 启用工具
     *
     * <p>将工具状态设置为启用，并注册到内存映射中。
     *
     * @param name    工具名称
     * @param version 版本号（可选，默认 1.0）
     * @return 操作结果
     */
    @PostMapping("/{name}/enable")
    public ResponseEntity<Map<String, Object>> enableTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        log.info("Enabling tool: {} v{}", name, version);

        Optional<ToolDefinitionEntity> entityOpt = repository.findByNameAndVersion(name, version);
        if (entityOpt.isEmpty()) {
            return ResponseEntity
                    .status(HttpStatus.NOT_FOUND)
                    .body(Map.of(
                            "error", "TOOL_NOT_FOUND",
                            "message", String.format("Tool '%s' version '%s' not found", name, version)
                    ));
        }

        ToolDefinitionEntity entity = entityOpt.get();
        if (entity.getEnabled()) {
            return ResponseEntity.ok(Map.of(
                    "message", "Tool is already enabled",
                    "name", name,
                    "version", version
            ));
        }

        // 更新状态
        entity.setEnabled(true);
        entity.setUpdatedAt(Instant.now());
        repository.save(entity);

        // 注册到内存
        ToolDefinition definition = convertToDefinition(entity);
        toolRegistry.register(definition);

        log.info("Tool enabled: {} v{}", name, version);
        return ResponseEntity.ok(Map.of(
                "message", "Tool enabled successfully",
                "name", name,
                "version", version
        ));
    }

    /**
     * 禁用工具
     *
     * <p>将工具状态设置为禁用，并从内存映射中移除。
     * 禁用的工具不会出现在工具列表中，但仍保留在数据库中。
     *
     * @param name    工具名称
     * @param version 版本号（可选，默认 1.0）
     * @return 操作结果
     */
    @PostMapping("/{name}/disable")
    public ResponseEntity<Map<String, Object>> disableTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        log.info("Disabling tool: {} v{}", name, version);

        Optional<ToolDefinitionEntity> entityOpt = repository.findByNameAndVersion(name, version);
        if (entityOpt.isEmpty()) {
            return ResponseEntity
                    .status(HttpStatus.NOT_FOUND)
                    .body(Map.of(
                            "error", "TOOL_NOT_FOUND",
                            "message", String.format("Tool '%s' version '%s' not found", name, version)
                    ));
        }

        ToolDefinitionEntity entity = entityOpt.get();
        if (!entity.getEnabled()) {
            return ResponseEntity.ok(Map.of(
                    "message", "Tool is already disabled",
                    "name", name,
                    "version", version
            ));
        }

        // 更新状态
        entity.setEnabled(false);
        entity.setUpdatedAt(Instant.now());
        repository.save(entity);

        // 从内存移除
        toolRegistry.unregister(name, version);

        log.info("Tool disabled: {} v{}", name, version);
        return ResponseEntity.ok(Map.of(
                "message", "Tool disabled successfully",
                "name", name,
                "version", version
        ));
    }

    /**
     * 列出所有工具
     *
     * <p>返回数据库中所有工具定义，包括禁用的工具。
     *
     * @param category 可选的类别过滤
     * @return 工具列表
     */
    @GetMapping
    public ResponseEntity<List<ToolDefinitionEntity>> listTools(
            @RequestParam(required = false) String category) {

        List<ToolDefinitionEntity> tools;
        if (category != null && !category.isBlank()) {
            tools = repository.findByCategory(category);
        } else {
            tools = repository.findAll();
        }

        return ResponseEntity.ok(tools);
    }

    /**
     * 获取工具详情
     *
     * @param name    工具名称
     * @param version 版本号（可选，默认 1.0）
     * @return 工具详情
     */
    @GetMapping("/{name}")
    public ResponseEntity<?> getTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        Optional<ToolDefinitionEntity> entityOpt = repository.findByNameAndVersion(name, version);
        if (entityOpt.isEmpty()) {
            return ResponseEntity
                    .status(HttpStatus.NOT_FOUND)
                    .body(Map.of(
                            "error", "TOOL_NOT_FOUND",
                            "message", String.format("Tool '%s' version '%s' not found", name, version)
                    ));
        }

        return ResponseEntity.ok(entityOpt.get());
    }

    /**
     * 删除工具
     *
     * <p>从数据库和内存映射中彻底删除工具。
     *
     * @param name    工具名称
     * @param version 版本号（可选，默认 1.0）
     * @return 操作结果
     */
    @DeleteMapping("/{name}")
    public ResponseEntity<Map<String, Object>> deleteTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        log.info("Deleting tool: {} v{}", name, version);

        Optional<ToolDefinitionEntity> entityOpt = repository.findByNameAndVersion(name, version);
        if (entityOpt.isEmpty()) {
            return ResponseEntity
                    .status(HttpStatus.NOT_FOUND)
                    .body(Map.of(
                            "error", "TOOL_NOT_FOUND",
                            "message", String.format("Tool '%s' version '%s' not found", name, version)
                    ));
        }

        ToolDefinitionEntity entity = entityOpt.get();
        repository.delete(entity);

        // 从内存移除
        toolRegistry.unregister(name, version);

        log.info("Tool deleted: {} v{}", name, version);
        return ResponseEntity.ok(Map.of(
                "message", "Tool deleted successfully",
                "name", name,
                "version", version
        ));
    }

    /**
     * 刷新工具注册表
     *
     * <p>从数据库重新加载所有启用的工具到内存映射。
     *
     * @return 刷新结果
     */
    @PostMapping("/refresh")
    public ResponseEntity<Map<String, Object>> refreshTools() {
        log.info("Refreshing tool registry from database");

        int count = toolRegistry.refresh();

        return ResponseEntity.ok(Map.of(
                "message", "Tool registry refreshed successfully",
                "toolCount", count
        ));
    }

    /**
     * 将 JPA 实体转换为内存对象
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
                .requiresApproval(entity.getEnabled() && entity.getRequiresApproval())
                .approvalCondition(entity.getApprovalCondition())
                .build();
    }

    /**
     * 工具注册请求
     *
     * @param name              工具名称
     * @param version           版本号
     * @param category          类别
     * @param description       描述
     * @param inputSchema       输入 Schema
     * @param outputSchema      输出 Schema
     * @param riskLevel         风险等级
     * @param requiresApproval  是否需要审批
     * @param approvalCondition 审批条件
     */
    public record ToolRegistrationRequest(
            String name,
            String version,
            String category,
            String description,
            String inputSchema,
            String outputSchema,
            String riskLevel,
            Boolean requiresApproval,
            String approvalCondition
    ) {}
}