package com.platform.toolbus.permission;

import lombok.Getter;

/**
 * 工具权限拒绝异常
 */
@Getter
public class ToolPermissionDeniedException extends RuntimeException {

    private final String errorCode;
    private final String toolName;
    private final String tenantId;

    public ToolPermissionDeniedException(String errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
        this.toolName = null;
        this.tenantId = null;
    }

    public ToolPermissionDeniedException(String errorCode, String message, String toolName, String tenantId) {
        super(message);
        this.errorCode = errorCode;
        this.toolName = toolName;
        this.tenantId = tenantId;
    }

    /**
     * 角色无权调用工具
     */
    public static ToolPermissionDeniedException roleNotAllowed(String toolName, String roleName) {
        return new ToolPermissionDeniedException(
            "TOOL_NOT_ALLOWED",
            String.format("角色 [%s] 无权调用工具 [%s]", roleName, toolName),
            toolName, null
        );
    }

    /**
     * 租户未开通工具
     */
    public static ToolPermissionDeniedException toolNotEnabledForTenant(String toolName, String tenantId) {
        return new ToolPermissionDeniedException(
            "TOOL_NOT_ENABLED_FOR_TENANT",
            String.format("租户 [%s] 未开通工具 [%s]", tenantId, toolName),
            toolName, tenantId
        );
    }

    /**
     * 工具被禁用
     */
    public static ToolPermissionDeniedException toolDisabled(String toolName, String reason) {
        return new ToolPermissionDeniedException(
            "TOOL_DISABLED",
            String.format("工具 [%s] 已被禁用: %s", toolName, reason),
            toolName, null
        );
    }

    /**
     * ABAC 条件不满足
     */
    public static ToolPermissionDeniedException abacConditionFailed(String condition) {
        return new ToolPermissionDeniedException(
            "ABAC_CONDITION_FAILED",
            String.format("ABAC 条件不满足: %s", condition)
        );
    }

    /**
     * 配额超出
     */
    public static ToolPermissionDeniedException quotaExceeded(String toolName, String quotaType) {
        return new ToolPermissionDeniedException(
            "QUOTA_EXCEEDED",
            String.format("工具 [%s] %s配额已用尽", toolName, quotaType),
            toolName, null
        );
    }
}
