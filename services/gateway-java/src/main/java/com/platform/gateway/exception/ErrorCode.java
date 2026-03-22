package com.platform.gateway.exception;

import lombok.Getter;

/**
 * 统一错误码枚举
 * 对应 Proto: common.error_code
 */
@Getter
public enum ErrorCode {

    // ====== 通用错误 (10xxx) ======
    ERR_UNKNOWN("ERR_UNKNOWN", "Unknown error", "未知错误", 500),
    ERR_INVALID_REQUEST("ERR_INVALID_REQUEST", "Invalid request", "请求参数有误", 400),
    ERR_UNAUTHORIZED("ERR_UNAUTHORIZED", "Unauthorized", "请先登录", 401),
    ERR_FORBIDDEN("ERR_FORBIDDEN", "Forbidden", "无权限访问", 403),
    ERR_NOT_FOUND("ERR_NOT_FOUND", "Resource not found", "资源不存在", 404),
    ERR_RATE_LIMITED("ERR_RATE_LIMITED", "Rate limit exceeded", "请求过于频繁", 429),
    ERR_TIMEOUT("ERR_TIMEOUT", "Request timeout", "请求超时", 504),
    ERR_SERVICE_UNAVAILABLE("ERR_SERVICE_UNAVAILABLE", "Service unavailable", "服务暂不可用", 503),

    // ====== Agent 编排错误 (20xxx) ======
    ERR_AGENT_MAX_STEPS_EXCEEDED("ERR_AGENT_MAX_STEPS_EXCEEDED", "Max steps exceeded", "任务复杂度过高", 400),
    ERR_AGENT_CONTEXT_TOO_LONG("ERR_AGENT_CONTEXT_TOO_LONG", "Context too long", "对话过长，请开启新会话", 400),
    ERR_AGENT_TOOL_NOT_FOUND("ERR_AGENT_TOOL_NOT_FOUND", "Tool not found", "工具不存在", 404),

    // ====== 模型网关错误 (30xxx) ======
    ERR_MODEL_ALL_PROVIDERS_DOWN("ERR_MODEL_ALL_PROVIDERS_DOWN", "All providers down", "AI服务暂不可用", 503),
    ERR_MODEL_CONTENT_FILTERED("ERR_MODEL_CONTENT_FILTERED", "Content filtered", "内容被安全过滤", 400),

    // ====== 工具总线错误 (40xxx) ======
    ERR_TOOL_VALIDATION_FAILED("ERR_TOOL_VALIDATION_FAILED", "Tool validation failed", "参数校验失败", 400),
    ERR_TOOL_EXECUTION_FAILED("ERR_TOOL_EXECUTION_FAILED", "Tool execution failed", "工具执行失败", 500),
    ERR_TOOL_RISK_REJECTED("ERR_TOOL_RISK_REJECTED", "Operation rejected by risk control", "操作被安全策略阻止", 403),
    ERR_TOOL_APPROVAL_REQUIRED("ERR_TOOL_APPROVAL_REQUIRED", "Approval required", "需要人工审批", 202),
    ERR_TOOL_NOT_FOUND("ERR_TOOL_NOT_FOUND", "Tool not found", "工具不存在", 404),
    ERR_TOOL_ALREADY_EXISTS("ERR_TOOL_ALREADY_EXISTS", "Tool already exists", "工具已存在", 409),

    // ====== 会话错误 (21xxx) ======
    ERR_SESSION_NOT_FOUND("ERR_SESSION_NOT_FOUND", "Session not found", "会话不存在", 404),
    ERR_SESSION_ARCHIVED("ERR_SESSION_ARCHIVED", "Session archived", "会话已归档", 400),

    // ====== 用户错误 (50xxx) ======
    ERR_USER_NOT_FOUND("ERR_USER_NOT_FOUND", "User not found", "用户不存在", 404),
    ERR_USER_ALREADY_EXISTS("ERR_USER_ALREADY_EXISTS", "User already exists", "用户已存在", 409),
    ERR_USER_DISABLED("ERR_USER_DISABLED", "User disabled", "用户已禁用", 403),

    // ====== 审批错误 (60xxx) ======
    ERR_APPROVAL_NOT_FOUND("ERR_APPROVAL_NOT_FOUND", "Approval not found", "审批不存在", 404),
    ERR_APPROVAL_EXPIRED("ERR_APPROVAL_EXPIRED", "Approval expired", "审批已过期", 400),
    ERR_APPROVAL_ALREADY_REVIEWED("ERR_APPROVAL_ALREADY_REVIEWED", "Already reviewed", "审批已处理", 409),

    // ====== 租户配额错误 (70xxx) ======
    ERR_TENANT_QUOTA_EXCEEDED("ERR_TENANT_QUOTA_EXCEEDED", "Tenant quota exceeded", "租户配额已用尽", 429);

    private final String code;
    private final String message;
    private final String userMessage;
    private final int httpStatus;

    ErrorCode(String code, String message, String userMessage, int httpStatus) {
        this.code = code;
        this.message = message;
        this.userMessage = userMessage;
        this.httpStatus = httpStatus;
    }
}
