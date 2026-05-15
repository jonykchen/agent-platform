package com.platform.toolbus.grpc;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.common.ErrorDetail;
import com.platform.common.ErrorCode;
import com.platform.toolbus.*;
import com.platform.toolbus.executor.MockToolExecutor;
import com.platform.toolbus.executor.ToolExecutionResult;
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
 * ToolBus gRPC 服务实现 (Mock)
 */
@Slf4j
@GrpcService
@RequiredArgsConstructor
public class ToolBusGrpcService extends ToolBusServiceGrpc.ToolBusServiceImplBase {

    private final ToolRegistry toolRegistry;
    private final MockToolExecutor mockToolExecutor;
    private final ObjectMapper objectMapper = new ObjectMapper();

    // 虚拟线程池（Java 21）
    private final ExecutorService virtualThreadExecutor = Executors.newVirtualThreadPerTaskExecutor();

    @Override
    public void executeTool(ToolExecuteRequest request, io.grpc.stub.StreamObserver<ToolExecuteResponse> responseObserver) {
        String requestId = request.getContext().getRequestId();
        String toolName = request.getToolName();

        log.info("ExecuteTool request: requestId={}, toolName={}", requestId, toolName);

        try {
            ToolExecutionResult result = mockToolExecutor.execute(
                    toolName,
                    request.getToolVersion(),
                    request.getArgumentsJson()
            );

            ToolExecuteResponse.Builder responseBuilder = ToolExecuteResponse.newBuilder()
                    .setContext(request.getContext())
                    .setCallId(result.getCallId())
                    .setStatus(result.getStatus())
                    .setRiskLevel(result.getRiskLevel() != null ? result.getRiskLevel() : "low")
                    .setDurationMs(result.getDurationMs())
                    .setWasCached(result.isWasCached());

            if ("success".equals(result.getStatus())) {
                responseBuilder.setResultJson(result.getResultJson() != null ? result.getResultJson() : "");
            } else if ("pending_approval".equals(result.getStatus())) {
                responseBuilder.setApprovalId(result.getApprovalId() != null ? result.getApprovalId() : "");
                responseBuilder.setApprovalReason(result.getApprovalReason() != null ? result.getApprovalReason() : "");
            } else {
                responseBuilder.setError(ErrorDetail.newBuilder()
                        .setCode(ErrorCode.ERR_TOOL_EXECUTION_FAILED)
                        .setMessage(result.getErrorMessage() != null ? result.getErrorMessage() : "Unknown error")
                        .build());
            }

            responseObserver.onNext(responseBuilder.build());
            responseObserver.onCompleted();

        } catch (Exception e) {
            log.error("ExecuteTool failed: requestId={}", requestId, e);
            responseObserver.onNext(buildErrorResponse(request, ErrorCode.ERR_TOOL_EXECUTION_FAILED, e.getMessage()));
            responseObserver.onCompleted();
        }
    }

    @Override
    public void executeToolsBatch(ToolsBatchRequest request,
            io.grpc.stub.StreamObserver<ToolsBatchResponse> responseObserver) {

        String requestId = request.getContext().getRequestId();
        int toolCount = request.getToolsCount();

        log.info("ExecuteToolsBatch request: requestId={}, count={}", requestId, toolCount);

        long startTime = System.currentTimeMillis();

        List<CompletableFuture<ToolExecuteResponse>> futures = request.getToolsList().stream()
                .map(toolRequest -> CompletableFuture.supplyAsync(
                        () -> executeToolInternal(toolRequest),
                        virtualThreadExecutor
                ))
                .collect(Collectors.toList());

        try {
            CompletableFuture.allOf(futures.toArray(new CompletableFuture[0])).join();

            List<ToolExecuteResponse> results = futures.stream()
                    .map(CompletableFuture::join)
                    .collect(Collectors.toList());

            long totalDurationMs = System.currentTimeMillis() - startTime;

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
            return buildErrorResponse(toolRequest, ErrorCode.ERR_TOOL_EXECUTION_FAILED, e.getMessage());
        }
    }

    @Override
    public void listTools(ListToolsRequest request,
            io.grpc.stub.StreamObserver<ListToolsResponse> responseObserver) {

        log.info("ListTools request: category={}", request.getCategory());

        List<ToolInfo> tools = toolRegistry.listAll().stream()
                .filter(tool -> {
                    if (!request.getCategory().isEmpty() && !tool.getCategory().equals(request.getCategory())) {
                        return false;
                    }
                    if (request.getIncludeDeprecated() && tool.isDeprecated()) {
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
                            .setCode(ErrorCode.ERR_AGENT_TOOL_NOT_FOUND)
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
                .setRequiresApproval(tool.isRequiresApproval())
                .setIsDeprecated(tool.isDeprecated())
                .build();
    }

    private ToolExecuteResponse buildErrorResponse(ToolExecuteRequest request,
                                                   ErrorCode errorCode, String errorMessage) {
        return ToolExecuteResponse.newBuilder()
                .setContext(request.getContext())
                .setStatus("failed")
                .setError(ErrorDetail.newBuilder()
                        .setCode(errorCode)
                        .setMessage(errorMessage != null ? errorMessage : "Unknown error")
                        .build())
                .build();
    }
}
