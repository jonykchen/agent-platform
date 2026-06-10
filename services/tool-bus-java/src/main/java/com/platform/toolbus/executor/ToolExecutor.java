package com.platform.toolbus.executor;

/**
 * 工具执行器接口
 *
 * <p>统一 Mock（开发）与 Real（生产）两种执行器的契约，由
 * {@code ToolBusGrpcService} 通过 Spring Profile 注入对应实现：
 * <ul>
 *   <li>{@code @Profile("dev"|"local"|"test")} → {@link MockToolExecutor}</li>
 *   <li>{@code @Profile("prod")} → {@link RealToolExecutor}</li>
 * </ul>
 *
 * <p>无论哪种实现，执行前都必须经过风险闸门（{@link ToolRiskGate}）：
 * 高风险 / 需审批的工具不直接执行，而是返回 {@code pending_approval} 状态，
 * 由编排层走人工审批中断流程（S-AGENT-06 五层鉴权第 5 层：风险等级）。
 */
public interface ToolExecutor {

    /**
     * 执行工具调用
     *
     * @param toolName      工具名称
     * @param version       工具版本
     * @param argumentsJson 参数（JSON 字符串）
     * @param tenantId      租户 ID（用于风险评估的租户级策略）
     * @param userId        发起用户 ID
     * @param runId         Agent 运行 ID（用于关联审批任务）
     * @return 执行结果（success / failed / pending_approval / rejected）
     */
    ToolExecutionResult execute(
            String toolName,
            String version,
            String argumentsJson,
            String tenantId,
            String userId,
            String runId
    );
}
