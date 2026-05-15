package com.platform.gateway.service;

import com.platform.gateway.dto.request.ChatRequest;
import com.platform.gateway.dto.response.ChatResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.OrchestratorServiceGrpc;
import com.platform.gateway.OrchestratorServiceGrpc.OrchestratorServiceBlockingStub;
import com.platform.gateway.RequestContext;
import com.platform.gateway.Message;
import com.platform.gateway.ToolCall;
// Note: ChatRequest and ChatResponse from proto are used with fully qualified names
import com.platform.common.ErrorDetail;
import com.platform.gateway.security.UserPrincipal;
import com.platform.gateway.util.RequestIdGenerator;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.Status;
import io.grpc.StatusRuntimeException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

/**
 * Orchestrator gRPC 客户端
 *
 * 【连接管理】
 * - 使用 ManagedChannel 单例
 * - Keepalive 心跳保持连接
 * - 自动重连机制
 *
 * 【调用流程】
 * 1. 构建请求上下文（request_id, tenant_id, user_id）
 * 2. 转换 DTO 到 Proto
 * 3. 发送 gRPC 调用
 * 4. 转换 Proto 到 DTO
 * 5. 处理异常
 *
 * 【异常处理】
 * - UNAVAILABLE: 服务不可用，返回 503
 * - DEADLINE_EXCEEDED: 超时，返回 504
 * - INTERNAL: 内部错误，返回 500
 */
@Slf4j
@Service
public class OrchestratorClient {

    @Value("${orchestrator.grpc.host:localhost}")
    private String orchestratorHost;

    @Value("${orchestrator.grpc.port:50051}")
    private int orchestratorPort;

    @Value("${orchestrator.grpc.timeout-ms:30000}")
    private int timeoutMs;

    @Value("${orchestrator.grpc.keepalive-time-ms:30000}")
    private int keepaliveTimeMs;

    private ManagedChannel channel;
    private OrchestratorServiceBlockingStub stub;

    /**
     * 初始化 gRPC Channel
     */
    private void initChannel() {
        if (channel == null || channel.isShutdown()) {
            channel = ManagedChannelBuilder.forAddress(orchestratorHost, orchestratorPort)
                    .usePlaintext()
                    .keepAliveTime(keepaliveTimeMs, TimeUnit.MILLISECONDS)
                    .keepAliveWithoutCalls(true)
                    .maxInboundMessageSize(16 * 1024 * 1024)  // 16MB
                    .enableRetry()
                    .build();

            stub = OrchestratorServiceGrpc.newBlockingStub(channel);

            log.info("gRPC channel initialized: {}:{}", orchestratorHost, orchestratorPort);
        }
    }

    /**
     * 发送对话请求到 Orchestrator
     */
    public ChatResponse sendChatRequest(ChatRequest request) {
        initChannel();

        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = getTenantId();
        String userId = getUserId();

        log.info("Sending chat request to Orchestrator: requestId={}, tenantId={}, userId={}",
                requestId, tenantId, userId);

        // 构建请求上下文
        RequestContext context = RequestContext.newBuilder()
                .setRequestId(requestId)
                .setTenantId(tenantId)
                .setUserId(userId)
                .setTraceId(requestId)  // 使用 request_id 作为 trace_id
                .build();

        // 转换历史消息
        List<Message> historyProto = request.getHistory()
                .stream()
                .map(h -> Message.newBuilder()
                        .setRole(h.getRole())
                        .setContent(h.getContent())
                        .build())
                .collect(Collectors.toList());

        // 构建请求 - 使用完全限定名避免歧义
        com.platform.gateway.ChatRequest grpcRequest = com.platform.gateway.ChatRequest.newBuilder()
                .setContext(context)
                .setMessage(request.getMessage())
                .addAllHistory(historyProto)
                .setModel(request.getModel() != null ? request.getModel() : "")
                .setTemperature(request.getTemperature() != null ? request.getTemperature().floatValue() : 0.7f)
                .setMaxTokens(request.getMaxTokens() != null ? request.getMaxTokens() : 2000)
                .setEnableTools(true)
                .setEnableRag(false)
                .build();

        try {
            // 发送请求
            com.platform.gateway.ChatResponse grpcResponse = stub
                    .withDeadlineAfter(timeoutMs, TimeUnit.MILLISECONDS)
                    .chatCompletion(grpcRequest);

            // 转换响应
            return ChatResponse.builder()
                    .requestId(grpcResponse.getContext().getRequestId())
                    .response(grpcResponse.getResponse())
                    .modelUsed(grpcResponse.getModelUsed())
                    .promptTokens(grpcResponse.getPromptTokens())
                    .completionTokens(grpcResponse.getCompletionTokens())
                    .totalTokens(grpcResponse.getTotalTokens())
                    .costUsd((double) grpcResponse.getCostUsd())
                    .createdAt(grpcResponse.getCreatedAt())
                    .latencyMs(grpcResponse.getLatencyMs())
                    .finishReason(grpcResponse.getFinishReason())
                    .build();

        } catch (StatusRuntimeException e) {
            log.error("gRPC call failed: requestId={}, status={}, message={}",
                    requestId, e.getStatus().getCode(), e.getMessage());

            handleGrpcException(e, requestId);
            return null;  // unreachable
        }
    }

    /**
     * 处理 gRPC 异常
     */
    private void handleGrpcException(StatusRuntimeException e, String requestId) {
        Status.Code code = e.getStatus().getCode();

        if (code == Status.Code.UNAVAILABLE) {
            throw new BusinessException(ErrorCode.ERR_SERVICE_UNAVAILABLE,
                "Orchestrator 服务暂时不可用，请稍后重试");
        }

        if (code == Status.Code.DEADLINE_EXCEEDED) {
            throw new BusinessException(ErrorCode.ERR_TIMEOUT,
                "请求处理超时，请稍后重试");
        }

        if (code == Status.Code.INTERNAL) {
            throw new BusinessException(ErrorCode.ERR_UNKNOWN,
                "内部服务错误");
        }

        throw new BusinessException(ErrorCode.ERR_UNKNOWN,
            "未知错误: " + e.getStatus().getDescription());
    }

    /**
     * 获取租户 ID
     */
    private String getTenantId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof UserPrincipal) {
            return ((UserPrincipal) auth.getPrincipal()).getTenantId();
        }
        return "default";
    }

    /**
     * 获取用户 ID
     */
    private String getUserId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.getPrincipal() instanceof UserPrincipal) {
            return ((UserPrincipal) auth.getPrincipal()).getUserId();
        }
        return "anonymous";
    }

    /**
     * 关闭 gRPC Channel
     */
    @PreDestroy
    public void shutdown() {
        if (channel != null && !channel.isShutdown()) {
            try {
                channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
                log.info("gRPC channel shutdown completed");
            } catch (InterruptedException e) {
                log.warn("gRPC channel shutdown interrupted");
                channel.shutdownNow();
            }
        }
    }
}
