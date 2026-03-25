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
 *
 * 【核心概念】为什么使用 gRPC 而非 REST？
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * gRPC vs REST 对比：
 * ┌─────────────────┬──────────────────────────┬──────────────────────────┐
 * │  特性            │  gRPC                    │  REST                    │
 * ├─────────────────┼──────────────────────────┼──────────────────────────┤
 * │  数据格式        │  Protobuf（二进制）       │  JSON（文本）            │
 * │  性能           │  快（体积小、序列化快）    │  较慢                    │
 * │  类型安全        │  强类型（.proto 定义）    │  弱类型                  │
 * │  流式传输        │  原生支持双向流           │  需额外实现（SSE/WebSocket）│
 * │  代码生成        │  自动生成客户端/服务端     │  需手动或 OpenAPI 工具   │
 * │  浏览器支持      │  需要 gRPC-Web 代理       │  原生支持                │
 * └─────────────────┴──────────────────────────┴──────────────────────────┘
 *
 * ToolBus 选择 gRPC 的原因：
 * 1. 内部服务通信：Orchestrator（Python）与 ToolBus（Java）都是后端服务
 * 2. 高频调用：工具调用频繁，需要高性能
 * 3. 强类型约束：Protobuf 定义接口，避免字段不一致
 * 4. 批量操作：executeToolsBatch 一次调用多个工具
 *
 * 【gRPC 调用模型】
 * ┌─────────────────────────────────────────────────────────────────────────┐
 * │  Orchestrator (Python)                                                  │
 * │       │                                                                 │
 * │       │ gRPC Stub (自动生成)                                             │
 * │       ▼                                                                 │
 * │  ┌─────────────────────────────────────────────────────────────────────┐│
 * │  │                     ToolBus (Java)                                  ││
 * │  │  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐      ││
 * │  │  │ executeTool   │    │ listTools     │    │ validateInput │      ││
 * │  │  │ (Unary)       │    │ (Unary)       │    │ (Unary)       │      ││
 * │  │  └───────────────┘    └───────────────┘    └───────────────┘      ││
 * │  └─────────────────────────────────────────────────────────────────────┘│
 * └─────────────────────────────────────────────────────────────────────────┘
 *
 * 【Protobuf 定义示例】（contracts/proto/toolbus/service.proto）
 * service ToolBusService {
 *   rpc ExecuteTool(ToolExecuteRequest) returns (ToolExecuteResponse);
 *   rpc ExecuteToolsBatch(ToolsBatchRequest) returns (ToolsBatchResponse);
 *   rpc ListTools(ListToolsRequest) returns (ListToolsResponse);
 * }
 *
 * 【参考】
 * - gRPC 官方文档: https://grpc.io/docs/
 * - Protobuf 语法: https://protobuf.dev/programming-guides/
 * - grpc-spring-boot-starter: https://yidongnan.github.io/grpc-spring-boot-starter/
 */
@Slf4j
@GrpcService
@RequiredArgsConstructor
public class ToolBusGrpcService extends ToolBusServiceGrpc.ToolBusServiceImplBase {

    private final ToolRegistry toolRegistry;
    private final MockToolExecutor mockToolExecutor;
    private final ToolPermissionService permissionService;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 执行单个工具调用
     *
     * 【处理流程】
     * 1. 检查工具是否存在（工具注册表）
     * 2. 权限检查（租户 + 用户 + 工具维度）
     * 3. 执行工具（Mock 或真实实现）
     * 4. 构建响应（包含风险等级、耗时等）
     *
     * 【响应状态】
     * - success: 执行成功，result_json 包含结果
     * - pending_approval: 需要审批，返回 approval_id
     * - rejected: 风控拒绝，error 包含原因
     * - failed: 执行失败，error 包含错误信息
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
            // 工具注册表维护所有可用工具的定义（名称、参数 Schema、风险等级）
            var toolOpt = toolRegistry.get(toolName, request.getToolVersion());
            if (toolOpt.isEmpty()) {
                responseObserver.onNext(buildErrorResponse(request,
                        "ERR_AGENT_TOOL_NOT_FOUND", "Tool not found: " + toolName));
                responseObserver.onCompleted();
                return;
            }

            ToolDefinition tool = toolOpt.get();

            // 2. 权限检查
            // 检查顺序：租户配置 → 用户权限 → 工具级别
            // skipRiskCheck 用于内部调用（已通过上层风控）
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
            // 当前使用 Mock 执行器，生产环境替换为真实实现
            ToolExecutionResult result = mockToolExecutor.execute(
                    toolName,
                    request.getToolVersion(),
                    request.getArgumentsJson()
            );

            // 4. 构建响应
            // 包含：调用 ID、状态、结果、风险等级、耗时
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
                // 高风险操作需要审批
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
     * 批量执行工具调用
     *
     * 【批处理优化】
     * - 减少网络往返：一次 RPC 调用执行多个工具
     * - 并行执行：工具间无依赖时可并行
     * - 结果聚合：统一返回所有结果
     *
     * 注意：当前实现为顺序执行，后续可优化为并行执行
     */
    @Override
    public void executeToolsBatch(ToolsBatchRequest request,
            io.grpc.stub.StreamObserver<ToolsBatchResponse> responseObserver) {

        log.info("ExecuteToolsBatch request: requestId={}, count={}",
                request.getContext().getRequestId(), request.getToolsCount());

        // TODO: 并行执行多个工具以提升性能
        // 当前为顺序执行，可使用 CompletableFuture 或虚拟线程并行化
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

    /**
     * 列出可用工具
     *
     * 【过滤条件】
     * - category: 按类别过滤（如 "query", "write"）
     * - includeDeprecated: 是否包含已废弃工具
     */
    @Override
    public void listTools(ListToolsRequest request,
            io.grpc.stub.StreamObserver<ListToolsResponse> responseObserver) {

        log.info("ListTools request: tenantId={}, category={}",
                request.getContext().getTenantId(), request.getCategory());

        List<ToolInfo> tools = toolRegistry.listAll().stream()
                .filter(tool -> {
                    // 类别过滤
                    if (!request.getCategory().isEmpty() && !tool.getCategory().equals(request.getCategory())) {
                        return false;
                    }
                    // 废弃工具过滤
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
     *
     * 返回工具的完整定义：
     * - 名称、版本、描述
     * - 输入参数 Schema（JSON Schema 格式）
     * - 风险等级
     * - 是否需要审批
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
     *
     * 【验证规则】
     * 1. JSON 格式校验
     * 2. 必填字段检查
     * 3. 类型匹配校验
     * 4. 业务规则校验
     *
     * 当前仅做 JSON 格式校验，后续可扩展为完整的 Schema 验证
     */
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