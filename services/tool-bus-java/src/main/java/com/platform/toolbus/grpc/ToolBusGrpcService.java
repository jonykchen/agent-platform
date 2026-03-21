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
import java.util.stream.Collectors;

/**
 * ToolBus gRPC 服务实现
 */
@Slf4j
@GrpcService
@RequiredArgsConstructor
public class ToolBusGrpcService extends ToolBusServiceGrpc.ToolBusServiceImplBase {

    private final ToolRegistry toolRegistry;
    private final MockToolExecutor mockToolExecutor;
    private final ToolPermissionService permissionService;
    private final ObjectMapper objectMapper = new ObjectMapper();

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

    @Override
    public void executeToolsBatch(ToolsBatchRequest request,
            io.grpc.stub.StreamObserver<ToolsBatchResponse> responseObserver) {

        log.info("ExecuteToolsBatch request: requestId={}, count={}",
                request.getContext().getRequestId(), request.getToolsCount());

        List<ToolExecuteResponse> results = request.getToolsList().stream()
                .map(toolRequest -> {
                    // 同步调用单个工具（简化实现）
                    try {
                        ToolExecutionResult result = mockToolExecutor.execute(
                                toolRequest.getToolName(),
                                toolRequest.getToolVersion(),
                                toolRequest.getArgumentsJson()
                        );
                        return ToolExecuteResponse.newBuilder()
                                .setContext(request.getContext())
                                .setCallId(result.getCallId())
                                .setStatus(result.getStatus())
                                .setResultJson(result.getResultJson() != null ? result.getResultJson() : "")
                                .setDurationMs(result.getDurationMs())
                                .build();
                    } catch (Exception e) {
                        return buildErrorResponse(toolRequest, "ERR_TOOL_EXECUTION_FAILED", e.getMessage());
                    }
                })
                .collect(Collectors.toList());

        ToolsBatchResponse response = ToolsBatchResponse.newBuilder()
                .setContext(request.getContext())
                .addAllResults(results)
                .setTotalDurationMs(results.stream().mapToInt(ToolExecuteResponse::getDurationMs).sum())
                .build();

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }

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

    @Override
    public void validateToolInput(ValidateToolInputRequest request,
            io.grpc.stub.StreamObserver<ValidateToolInputResponse> responseObserver) {

        log.info("ValidateToolInput request: toolName={}", request.getToolName());

        // 简化实现：解析 JSON 判断是否有效
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