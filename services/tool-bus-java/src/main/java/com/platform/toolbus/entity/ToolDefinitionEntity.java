package com.platform.toolbus.entity;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.UUID;

/**
 * 工具定义实体
 *
 * <p>映射 {@code tool_definition} 表，存储工具的完整定义信息，包括：
 * <ul>
 *   <li>工具名称、版本、类别</li>
 *   <li>输入/输出 Schema（JSON Schema 格式）</li>
 *   <li>风险等级与审批要求</li>
 *   <li>启用状态</li>
 * </ul>
 *
 * <p>支持动态注册工具，无需重启服务。
 *
 * <h2>设计模式</h2>
 * <p>采用 Active Record 风格，通过 Spring Data JPA 的 Repository 模式访问。
 *
 * <h2>版本管理</h2>
 * <ul>
 *   <li>工具可多版本共存（v1.0, v2.0）</li>
 *   <li>版本号采用语义化版本（SemVer）</li>
 *   <li>同一工具名称 + 版本号唯一</li>
 * </ul>
 *
 * @see com.platform.toolbus.registry.ToolRegistry
 * @see com.platform.toolbus.repository.ToolDefinitionRepository
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "tool_definition", uniqueConstraints = {
    @UniqueConstraint(columnNames = {"name", "version"})
})
public class ToolDefinitionEntity {

    /**
     * 主键 ID
     */
    @Id
    @GeneratedValue
    private UUID id;

    /**
     * 工具名称
     *
     * <p>命名规范：{@code verb_noun}，如 {@code query_order_status}
     */
    @Column(name = "name", nullable = false, length = 128)
    private String name;

    /**
     * 工具版本
     *
     * <p>采用语义化版本格式，如 {@code 1.0}, {@code 2.1.0}
     */
    @Column(name = "version", nullable = false, length = 16)
    @Builder.Default
    private String version = "1.0";

    /**
     * 工具类别
     *
     * <p>可选值：
     * <ul>
     *   <li>{@code query} - 查询类工具（只读）</li>
     *   <li>{@code write} - 写操作工具</li>
     *   <li>{@code external} - 外部服务集成工具</li>
     * </ul>
     */
    @Column(name = "category", nullable = false, length = 32)
    private String category;

    /**
     * 工具描述
     */
    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    /**
     * 输入参数 Schema（JSON Schema 格式）
     *
     * <p>用于参数校验和 API 文档生成
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "input_schema", columnDefinition = "jsonb")
    private String inputSchema;

    /**
     * 输出参数 Schema（JSON Schema 格式）
     *
     * <p>可选字段，用于响应校验
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "output_schema", columnDefinition = "jsonb")
    private String outputSchema;

    /**
     * 风险等级
     *
     * <p>可选值：
     * <ul>
     *   <li>{@code low} - 低风险（只读操作）</li>
     *   <li>{@code medium} - 中风险（有限写操作）</li>
     *   <li>{@code high} - 高风险（敏感操作）</li>
     *   <li>{@code critical} - 极高风险（核心业务影响）</li>
     * </ul>
     */
    @Column(name = "risk_level", nullable = false, length = 16)
    @Builder.Default
    private String riskLevel = "low";

    /**
     * 是否需要审批
     *
     * <p>高风险工具默认需要人工审批
     */
    @Column(name = "requires_approval", nullable = false)
    @Builder.Default
    private Boolean requiresApproval = false;

    /**
     * 审批条件表达式（JSON 格式）
     *
     * <p>示例：{@code {"amount": {"$gt": 10000}}}
     * <p>当条件满足时触发审批流程
     */
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "approval_condition", columnDefinition = "jsonb")
    private String approvalCondition;

    /**
     * 是否启用
     *
     * <p>禁用的工具不会出现在工具列表中
     */
    @Column(name = "enabled", nullable = false)
    @Builder.Default
    private Boolean enabled = true;

    /**
     * 创建时间
     */
    @Column(name = "created_at", nullable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();

    /**
     * 更新时间
     */
    @Column(name = "updated_at", nullable = false)
    @Builder.Default
    private Instant updatedAt = Instant.now();

    /**
     * 更新时间戳，自动设置为当前时间
     */
    @PreUpdate
    public void preUpdate() {
        this.updatedAt = Instant.now();
    }
}
