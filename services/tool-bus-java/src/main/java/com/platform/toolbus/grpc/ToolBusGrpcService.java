package com.platform.toolbus.grpc;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.toolbus.executor.MockToolExecutor;
import com.platform.toolbus.executor.ToolExecutionResult;
import com.platform.toolbus.permission.ToolPermissionService;
import com.platform.toolbus.registry.ToolDefinition;
import com.platform.toolbus.registry.ToolRegistry;
import io.grpc.Status;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import net.devh.boot.grpc.server.service.GrpcService;

import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

/**
 * ToolBus gRPC 服务实现
 *
 * 【并行执行优化】
 * 使用 CompletableFuture 实现工具并行调用：
 * - 无依赖的工具可同时执行
 * - 减少总耗时（从串行变为并行）
 * - 保持错误处理一致性
 */
@Slf4j
@GrpcService
@RequiredArgsConstructor
public class ToolBusGrpcService extends ToolBusServiceGrpc.ToolBusServiceImplBase {

    private final ToolRegistry toolRegistry;
    private final MockToolExecutor mockToolExecutor;
    private final ToolPermissionService permissionService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    // 虚拟线程池（Java 21）
    private final ExecutorService virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();

    /**
     * 执行单个工具调用
     */
    @Override
    public void executeTool(ToolExecuteRequest request, io.grpc.stub.StreamObserver<ToolExecuteResponse> responseObserver) {
        String requestId = request.getContext().getRequestId();
        String tenantId = request.getContext().getTenantId();
        String userId = request.getContext().getUserId();
        String toolName = request.getToolName();

        log.info("ExecuteTool request: requestId={}, tenantId={}, toolName={}",
                requestId, tenantId, toolName);

        try {
            // 1. 检查工具是否存在
            var toolOpt = toolRegistry.get(toolName, request.getToolVersion());
            if (toolOpt.isEmpty()) {
                responseObserver.onNext(buildErrorResponse(request,
                        "ERR_AGENT_TOOL_NOT_FOUND", "Tool not found: " + toolName));
                responseObserver.onCompleted();
                return;
            }

            ToolDefinition tool = toolOpt.get();

            // 2. 权限检查
            if (!request.getSkipRiskCheck()) {
                var permissionCheck = permissionService.checkPermission(tenantId, userId, toolName);
                if (!permissionCheck.isAllowed()) {
                    responseObserver.onNext(buildErrorResponse(request,
                            "ERR_PERMISSION_DENIED", permissionCheck.getReason()));
                    responseObserver.onCompleted();
                    return;
                }
            }

            // 3. 执行工具
            ToolExecutionResult result = mockToolExecutor.execute(
                    toolName,
                    request.getToolVersion(),
                    request.getArgumentsJson()
            );

            // 4. 构建响应
            ToolExecuteResponse.Builder responseBuilder = ToolExecuteResponse.newBuilder()
                    .setContext(request.getContext())
                    .setCallId(result.getCallId())
                    .setStatus(result.getStatus())
                    .setRiskLevel(tool.getRiskLevel())
                    .setDurationMs(result.getDurationMs())
                    .setWasCached(result.getWasCached());

            if (result.getStatus().equals("success")) {
                responseBuilder.setResultJson(result.getResultJson());
            } else if (result.getStatus().equals("pending_approval")) {
                responseBuilder.setApprovalId(result.getApprovalId());
                responseBuilder.setApprovalReason(result.getApprovalReason());
            } else {
                responseBuilder.setError(ErrorDetail.newBuilder()
                        .setCode(result.getErrorCode())
                        .setMessage(result.getErrorMessage())
                        .build());
            }

            responseObserver.onNext(responseBuilder.build());
            responseObserver.onCompleted();

            log.info("ExecuteTool completed: requestId={}, status={}", requestId, result.getStatus());

        } catch (Exception e) {
            log.error("ExecuteTool failed: requestId={}", requestId, e);
            responseObserver.onNext(buildErrorResponse(request,
                    "ERR_TOOL_EXECUTION_FAILED", e.getMessage()));
            responseObserver.onCompleted();
        }
    }

    /**
     * 批量执行工具调用 - 并行优化
     *
     * 【并行执行策略】
     * 1. 使用 CompletableFuture 异步执行每个工具
     * 2. 使用虚拟线程（Java 21）避免线程池阻塞
     * 3. 等待所有结果完成后统一返回
     * 4. 错误隔离：单个工具失败不影响其他工具
     *
     * 【性能提升】
     * - 串行：总耗时 = Σ 单个工具耗时
     * - 并行：总耗时 ≈ Max 单个工具耗时
     */
    @Override
    public void executeToolsBatch(ToolsBatchRequest request,
            io.grpc.stub.StreamObserver<ToolsBatchResponse> responseObserver) {

        String requestId = request.getContext().getRequestId();
        int toolCount = request.getToolsCount();

        log.info("ExecuteToolsBatch request: requestId={}, count={}", requestId, toolCount);

        long startTime = System.currentTimeMillis();

        // 并行执行所有工具
        List<CompletableFuture<ToolExecuteResponse>> futures = request.getToolsList().stream()
                .map(toolRequest -> CompletableFuture.supplyAsync(
                        () -> executeToolInternal(toolRequest),
                        virtualThreadExecutor
                ))
                .collect(Collectors.toList());

        // 等待所有结果
        CompletableFuture<Void> allFutures = CompletableFuture.allOf(
                futures.toArray(new CompletableFuture[0])
        );

        try {
            // 阻塞等待（虚拟线程不会阻塞平台线程）
            allFutures.join();

            // 收集结果
            List<ToolExecuteResponse> results = futures.stream()
                    .map(CompletableFuture::join)
                    .collect(Collectors.toList());

            long totalDurationMs = System.currentTimeMillis() - startTime;

            log.info("ExecuteToolsBatch completed: requestId={}, count={}, parallelDurationMs={}",
                    requestId, results.size(), totalDurationMs);

            ToolsBatchResponse response = ToolsBatchResponse.newBuilder()
                    .setContext(request.getContext())
                    .addAllResults(results)
                    .setTotalDurationMs((int) totalDurationMs)
                    .build();

            responseObserver.onNext(response);
            responseObserver.onCompleted();

        } catch (Exception e) {
            log.error("ExecuteToolsBatch failed: requestId={}", requestId, e);
            responseObserver.onError(Status.INTERNAL
                    .withDescription("Batch execution failed: " + e.getMessage())
                    .asRuntimeException());
        }
    }

    /**
     * 内部执行工具（用于并行调用）
     */
    private ToolExecuteResponse executeToolInternal(ToolExecuteRequest toolRequest) {
        try {
            ToolExecutionResult result = mockToolExecutor.execute(
                    toolRequest.getToolName(),
                    toolRequest.getToolVersion(),
                    toolRequest.getArgumentsJson()
            );

            return ToolExecuteResponse.newBuilder()
                    .setContext(toolRequest.getContext())
                    .setCallId(result.getCallId())
                    .setStatus(result.getStatus())
                    .setResultJson(result.getResultJson() != null ? result.getResultJson() : "")
                    .setDurationMs(result.getDurationMs())
                    .build();

        } catch (Exception e) {
            return buildErrorResponse(toolRequest, "ERR_TOOL_EXECUTION_FAILED", e.getMessage());
        }
    }

    /**
     * 列出可用工具
     */
    @Override
    public void listTools(ListToolsRequest request,
            io.grpc.stub.StreamObserver<ListToolsResponse> responseObserver) {

        log.info("ListTools request: tenantId={}, category={}",
                request.getContext().getTenantId(), request.getCategory());

        List<ToolInfo> tools = toolRegistry.listAll().stream()
                .filter(tool -> {
                    if (!request.getCategory().isEmpty() && !tool.getCategory().equals(request.getCategory())) {
                        return false;
                    }
                    if (!request.getIncludeDeprecated() && tool.isDeprecated()) {
                        return false;
                    }
                    return true;
                })
                .map(this::toToolInfo)
                .collect(Collectors.toList());

        ListToolsResponse response = ListToolsResponse.newBuilder()
                .setContext(request.getContext())
                .addAllTools(tools)
                .setTotalCount(tools.size())
                .build();

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }

    /**
     * 获取工具详情
     */
    @Override
    public void getToolInfo(GetToolInfoRequest request,
            io.grpc.stub.StreamObserver<GetToolInfoResponse> responseObserver) {

        log.info("GetToolInfo request: toolName={}", request.getToolName());

        var toolOpt = toolRegistry.get(request.getToolName(), request.getToolVersion());

        if (toolOpt.isEmpty()) {
            GetToolInfoResponse response = GetToolInfoResponse.newBuilder()
                    .setContext(request.getContext())
                    .setError(ErrorDetail.newBuilder()
                            .setCode("ERR_AGENT_TOOL_NOT_FOUND")
                            .setMessage("Tool not found: " + request.getToolName())
                            .build())
                    .build();
            responseObserver.onNext(response);
            responseObserver.onCompleted();
            return;
        }

        GetToolInfoResponse response = GetToolInfoResponse.newBuilder()
                .setContext(request.getContext())
                .setTool(toToolInfo(toolOpt.get()))
                .build();

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }

    /**
     * 验证工具输入参数
     */
    @Override
    public void validateToolInput(ValidateToolInputRequest request,
            io.grpc.stub.StreamObserver<ValidateToolInputResponse> responseObserver) {

        log.info("ValidateToolInput request: toolName={}", request.getToolName());

        boolean valid = true;
        List<ValidationError> errors = List.of();

        try {
            objectMapper.readValue(request.getArgumentsJson(), Map.class);
        } catch (Exception e) {
            valid = false;
            errors = List.of(ValidationError.newBuilder()
                    .setField("arguments")
                    .setMessage("Invalid JSON: " + e.getMessage())
                    .setCode("ERR_INVALID_JSON")
                    .build());
        }

        ValidateToolInputResponse response = ValidateToolInputResponse.newBuilder()
                .setContext(request.getContext())
                .setValid(valid)
                .addAllErrors(errors)
                .build();

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }

    /**
     * 转换工具定义为 Protobuf 消息
     */
    private ToolInfo toToolInfo(ToolDefinition tool) {
        return ToolInfo.newBuilder()
                .setName(tool.getName())
                .setVersion(tool.getVersion())
                .setCategory(tool.getCategory())
                .setDescription(tool.getDescription())
                .setInputSchemaJson(tool.getInputSchema())
                .setRiskLevel(tool.getRiskLevel())
                .setRequiresApproval(tool.getRequiresApproval())
                .setIsDeprecated(tool.isDeprecated())
                .build();
    }

    /**
     * 构建错误响应
     */
    private ToolExecuteResponse buildErrorResponse(ToolExecuteRequest request,
            String errorCode, String errorMessage) {
        return ToolExecuteResponse.newBuilder()
                .setContext(request.getContext())
                .setStatus("failed")
                .setError(ErrorDetail.newBuilder()
                        .setCode(errorCode)
                        .setMessage(errorMessage)
                        .build())
                .build();
    }
}