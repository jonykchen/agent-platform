package com.platform.toolbus.executor;

import lombok.Builder;
import lombok.Data;

/**
 * 工具执行上下文
 * 包含调用者的身份和租户信息
 */
@Data
@Builder
public class ToolExecutionContext {

    /**
     * 租户 ID
     */
    private String tenantId;

    /**
     * 用户 ID
     */
    private String userId;

    /**
     * 角色名称
     */
    private String roleName;

    /**
     * 请求 ID（用于追踪）
     */
    private String requestId;

    /**
     * 会话 ID
     */
    private String sessionId;

    /**
     * 运行实例 ID
     */
    private String runId;

    /**
     * 创建默认上下文（用于测试）
     */
    public static ToolExecutionContext defaultContext() {
        return ToolExecutionContext.builder()
            .tenantId("default")
            .userId("test_user")
            .roleName("admin")
            .requestId("req_test")
            .build();
    }
}
