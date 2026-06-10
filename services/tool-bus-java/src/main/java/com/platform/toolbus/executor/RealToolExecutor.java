package com.platform.toolbus.executor;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.toolbus.registry.ToolDefinition;
import com.platform.toolbus.registry.ToolRegistry;
import com.platform.toolbus.tools.RealTool;
import jakarta.annotation.PreDestroy;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * 真实工具执行器（生产环境）
 *
 * <p>替代 {@link MockToolExecutor}，将工具调用分发到实现了 {@link RealTool}
 * 接口的真实工具 Bean（如 PaymentTool / OrderQueryTool / UserInfoTool）。
 *
 * <p>【关键能力】
 * <ul>
 *   <li><b>风险闸门</b>：执行前经过 {@link ToolRiskGate}，高风险/需审批工具
 *       返回 {@code pending_approval}，不直接执行（审批闭环，P0-3）</li>
 *   <li><b>虚拟线程</b>：每次工具调用在虚拟线程上执行（Java 21），避免阻塞
 *       平台线程，激活此前已配置但未使用的虚拟线程能力</li>
 *   <li><b>超时控制</b>：单工具执行超时 {@value #TOOL_TIMEOUT_SECONDS}s（S-AGENT-08）</li>
 * </ul>
 *
 * <p>仅在 {@code prod} Profile 激活；开发/测试用 {@link MockToolExecutor}。
 */
@Slf4j
@Component
@Profile("prod")
public class RealToolExecutor implements ToolExecutor {

    /** 单工具执行超时（秒），对齐 S-AGENT-08 TOOL_CALL_TIMEOUT_S */
    static final int TOOL_TIMEOUT_SECONDS = 15;

    private final ToolRegistry toolRegistry;
    private final ToolRiskGate riskGate;
    private final ObjectMapper objectMapper;

    /** 工具名 → RealTool 实现的索引 */
    private final Map<String, RealTool> toolIndex = new ConcurrentHashMap<>();

    /** 虚拟线程池（Java 21）：每个任务一条虚拟线程 */
    private final ExecutorService virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();

    public RealToolExecutor(ToolRegistry toolRegistry,
                            ToolRiskGate riskGate,
                            ObjectMapper objectMapper,
                            java.util.List<RealTool> tools) {
        this.toolRegistry = toolRegistry;
        this.riskGate = riskGate;
        this.objectMapper = objectMapper;
        for (RealTool tool : tools) {
            toolIndex.put(tool.getName(), tool);
        }
        log.info("RealToolExecutor initialized with {} real tools: {}",
                toolIndex.size(), toolIndex.keySet());
    }

    @Override
    public ToolExecutionResult execute(String toolName, String version, String argumentsJson,
                                       String tenantId, String userId, String runId) {
        String callId = UUID.randomUUID().toString().replace("-", "").substring(0, 16);
        long startTime = System.currentTimeMillis();

        ToolDefinition definition = toolRegistry.get(toolName, version).orElse(null);

        // ========= 风险闸门：执行前评估，需审批则不执行 =========
        ToolRiskGate.Decision decision = riskGate.evaluate(definition, toolName, argumentsJson);
        if (decision.requiresApproval()) {
            log.info("Tool '{}' gated for approval: tenant={}, user={}, runId={}, reason={}",
                    toolName, tenantId, userId, runId, decision.reason());
            return riskGate.toPendingApproval(callId, decision);
        }

        // ========= 查找真实工具实现 =========
        RealTool tool = toolIndex.get(toolName);
        if (tool == null) {
            return ToolExecutionResult.builder()
                    .callId(callId)
                    .status("failed")
                    .errorCode("ERR_AGENT_TOOL_NOT_FOUND")
                    .errorMessage("Real tool not found: " + toolName)
                    .build();
        }

        // ========= 虚拟线程执行 + 超时控制 =========
        Map<String, Object> args;
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> parsed = objectMapper.readValue(argumentsJson, Map.class);
            args = parsed;
        } catch (Exception e) {
            return ToolExecutionResult.builder()
                    .callId(callId)
                    .status("failed")
                    .errorCode("ERR_TOOL_VALIDATION_FAILED")
                    .errorMessage("Invalid arguments JSON: " + e.getMessage())
                    .build();
        }

        Future<String> future = virtualThreadExecutor.submit(() -> tool.execute(args));
        try {
            String resultJson = future.get(TOOL_TIMEOUT_SECONDS, TimeUnit.SECONDS);
            int duration = (int) (System.currentTimeMillis() - startTime);
            return ToolExecutionResult.builder()
                    .callId(callId)
                    .status("success")
                    .resultJson(resultJson != null ? resultJson : "")
                    .riskLevel(decision.riskLevel())
                    .wasCached(false)
                    .durationMs(duration)
                    .build();

        } catch (TimeoutException e) {
            future.cancel(true);
            log.error("Tool '{}' execution timeout after {}s", toolName, TOOL_TIMEOUT_SECONDS);
            return ToolExecutionResult.builder()
                    .callId(callId)
                    .status("timeout")
                    .errorCode("ERR_TOOL_EXECUTION_FAILED")
                    .errorMessage("Tool execution timeout after " + TOOL_TIMEOUT_SECONDS + "s")
                    .build();

        } catch (Exception e) {
            log.error("Tool '{}' execution failed", toolName, e);
            return ToolExecutionResult.builder()
                    .callId(callId)
                    .status("failed")
                    .errorCode("ERR_TOOL_EXECUTION_FAILED")
                    .errorMessage(e.getCause() != null ? e.getCause().getMessage() : e.getMessage())
                    .build();
        }
    }

    @PreDestroy
    public void shutdown() {
        virtualThreadExecutor.shutdown();
        try {
            if (!virtualThreadExecutor.awaitTermination(10, TimeUnit.SECONDS)) {
                virtualThreadExecutor.shutdownNow();
            }
        } catch (InterruptedException e) {
            virtualThreadExecutor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}
