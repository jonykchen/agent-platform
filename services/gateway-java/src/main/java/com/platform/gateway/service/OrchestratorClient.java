package com.platform.gateway.service;

import com.platform.gateway.dto.request.ChatRequest;
import com.platform.gateway.dto.response.ChatResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

/**
 * Orchestrator gRPC 客户端
 * ADR-003: 统一用 gRPC
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class OrchestratorClient {

    @Value("${orchestrator.grpc.host:localhost}")
    private String orchestratorHost;

    @Value("${orchestrator.grpc.port:50051}")
    private int orchestratorPort;

    @Value("${orchestrator.grpc.timeout-ms:30000}")
    private int timeoutMs;

    /**
     * 发送对话请求到 Orchestrator
     */
    public ChatResponse sendChatRequest(ChatRequest request) {
        String requestId = RequestIdGenerator.getCurrent();

        // TODO: 实现 gRPC 调用
        // 当前返回 Mock 响应，等待 gRPC 代码生成后实现
        log.info("Sending chat request to Orchestrator: requestId={}, host={}:{}",
                requestId, orchestratorHost, orchestratorPort);

        // Mock 响应（Phase 1 MVP）
        return ChatResponse.builder()
                .requestId(requestId)
                .response("收到您的请求：" + request.getMessage() + "\n\n（Orchestrator 服务待连接）")
                .modelUsed("mock")
                .promptTokens(10)
                .completionTokens(20)
                .totalTokens(30)
                .costUsd(0.0)
                .createdAt(System.currentTimeMillis())
                .latencyMs(100)
                .finishReason("stop")
                .build();
    }
}