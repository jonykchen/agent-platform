package com.platform.toolbus.registry;

import lombok.Builder;
import lombok.Data;

/**
 * 工具定义
 */
@Data
@Builder
public class ToolDefinition {

    private String name;
    private String version;
    private String category;        // query / write / external
    private String description;
    private String inputSchema;      // JSON Schema
    private String outputSchema;     // JSON Schema
    private String riskLevel;       // low / medium / high / critical
    private boolean requiresApproval;
    private String approvalCondition;  // JSON 条件表达式
}
