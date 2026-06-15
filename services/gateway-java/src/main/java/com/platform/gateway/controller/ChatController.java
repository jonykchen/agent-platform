package com.platform.gateway.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.audit.AuditLog;
import com.platform.gateway.dto.request.ChatRequest;
import com.platform.gateway.dto.response.ChatResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.FastPathService;
import com.platform.gateway.service.OrchestratorClient;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.annotation.PreDestroy;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import org.slf4j.MDC;

/**
 * 对话控制器
 *
 * 【核心职责】
 * 1. 接收用户对话请求
 * 2. 快速路径判断（简单问答直接响应）
 * 3. 转发到 Orchestrator Python 服务
 * 4. 返回对话响应
 *
 * 【请求处理流程】
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          ChatController 流程                                │
 * │                                                                             │
 * │   POST /api/v1/chat/completions                                             │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  TenantContextFilter (前置)                                       │    │
 * │   │  - 提取 X-Tenant-ID, X-User-ID                                    │    │
 * │   │  - 设置 TenantContext                                             │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  FastPathService.isFastPath()                                    │    │
 * │   │  - 判断是否为简单问候                                              │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │            ┌─────────────┴─────────────┐                                  │
 * │            │                           │                                  │
 * │        [是快速路径]                 [否快速路径]                          │
 * │            │                           │                                  │
 * │            ▼                           ▼                                  │
 * │   直接返回预定义响应           调用 OrchestratorClient                    │
 * │   (延迟 < 50ms)                │                                         │
 * │                                ▼                                         │
 * │                    Orchestrator Python 服务                              │
 * │                    │                                                      │
 * │                    ▼                                                      │
 * │                    LangGraph Agent 编排                                   │
 * │                    │                                                      │
 * │                    ▼                                                      │
 * │                    返回 ChatResponse                                      │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *
 * 【技术选型】异常处理策略
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 策略               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ BusinessException  │ • 统一错误格式              │ • 需维护 ErrorCode 枚举     │
 * │ (当前选择)         │ • 前端易于处理              │                              │
 * │                    │ • 符合 S-JAVA-09            │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ HTTP 状态码        │ • REST 标准                 │ • 无法携带业务错误码        │
 * │                    │                             │ • 前端需额外处理            │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 直接抛异常         │ • 简单                      │ • 异常栈暴露                │
 * │                    │                             │ • 不安全                    │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【日志规范】
 * - INFO: 请求开始/结束，关键指标（tokens, latency）
 * - DEBUG: 快速路径判断详情
 * - ERROR: 调用失败，包含 requestId 便于追踪
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor
public class ChatController {

    private final FastPathService fastPathService;
    private final OrchestratorClient orchestratorClient;
    private final TenantContextService tenantContextService;
    private final ObjectMapper objectMapper;

    // 有界线程池：核心线程 10，最大线程 50，队列容量 100，拒绝策略为调用者运行
    private final ExecutorService executor = new ThreadPoolExecutor(
        10, 50, 60L, TimeUnit.SECONDS,
        new LinkedBlockingQueue<>(100),
        new ThreadPoolExecutor.CallerRunsPolicy()
    );

    @PreDestroy
    public void shutdown() {
        executor.shutdown();
        try {
            if (!executor.awaitTermination(10, java.util.concurrent.TimeUnit.SECONDS)) {
                executor.shutdownNow();
            }
        } catch (InterruptedException e) {
            executor.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }

    /**
     * 对话补全接口（SSE 流式响应）
     */
    @PostMapping(value = "/completions", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @AuditLog(
        type = "agent.run_started",
        category = "business",
        action = "发起对话",
        resourceType = "agent_run",
        severity = "info",
        logArguments = false
    )
    public SseEmitter chatCompletion(@Valid @RequestBody ChatRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Chat request: requestId={}, tenant={}, user={}, message={}",
                requestId, tenantId, userId, truncate(request.getMessage(), 100));

        // 创建 SSE Emitter（超时 5 分钟）
        SseEmitter emitter = new SseEmitter(300000L);

        // SSE 生命周期回调：防止客户端断连后 gRPC stream 继续运行造成资源泄露
        AtomicReference<Runnable> streamCancelRef = new AtomicReference<>(() -> {});

        emitter.onTimeout(() -> {
            log.warn("SSE emitter timeout: requestId={}", requestId);
            streamCancelRef.get().run();
        });
        emitter.onError(ex -> {
            log.warn("SSE emitter error: requestId={}, error={}", requestId, ex.getMessage());
            streamCancelRef.get().run();
        });
        emitter.onCompletion(() -> {
            log.debug("SSE emitter completed: requestId={}", requestId);
            streamCancelRef.get().run();
        });

        // 传播 MDC 上下文到异步线程（确保 tenant_id/user_id/request_id 在日志中可追踪）
        Map<String, String> mdcContext = MDC.getCopyOfContextMap();

        executor.execute(() -> {
            if (mdcContext != null) {
                MDC.setContextMap(mdcContext);
            }
            try {
            try {
                // 快速路径判断：简单问答直接透传，不经过完整 Agent 编排（单块下发）
                if (fastPathService.isFastPath(request)) {
                    log.debug("Fast path detected for request {}", requestId);
                    ChatResponse response = fastPathService.handleFastPath(request);

                    emitter.send(SseEmitter.event()
                            .name("message")
                            .data(objectMapper.writeValueAsString(Map.of(
                                    "delta_content", response.getResponse(),
                                    "is_final", false
                            ))));
                    emitter.send(SseEmitter.event()
                            .name("message")
                            .data(objectMapper.writeValueAsString(Map.of(
                                    "delta_content", "",
                                    "is_final", true,
                                    "usage", Map.of(
                                            "prompt_tokens", response.getPromptTokens(),
                                            "completion_tokens", response.getCompletionTokens(),
                                            "total_tokens", response.getTotalTokens()
                                    )
                            ))));
                    emitter.complete();
                    return;
                }

                // 正常路径：调用 Orchestrator 流式接口，逐块转发为 SSE（端到端真流式）
                orchestratorClient.streamChatRequest(request, chunk -> {
                    try {
                        // 错误块：发送 error 事件并终止
                        if (chunk.hasError()) {
                            emitter.send(SseEmitter.event()
                                    .name("error")
                                    .data(objectMapper.writeValueAsString(Map.of(
                                            "error", chunk.getError().getCode().name(),
                                            "message", chunk.getError().getUserMessage()
                                    ))));
                            return;
                        }

                        String finishReason = chunk.getFinishReason();
                        boolean isFinal = finishReason != null && !finishReason.isEmpty();

                        emitter.send(SseEmitter.event()
                                .name("message")
                                .data(objectMapper.writeValueAsString(Map.of(
                                        "delta_content", chunk.getDelta(),
                                        "is_final", isFinal,
                                        "finish_reason", finishReason
                                ))));
                    } catch (IOException ioe) {
                        throw new RuntimeException(ioe);
                    }
                });

                log.info("Chat stream completed: requestId={}", requestId);
                emitter.complete();

            } catch (BusinessException e) {
                try {
                    emitter.send(SseEmitter.event()
                            .name("error")
                            .data(objectMapper.writeValueAsString(Map.of(
                                    "error", e.getErrorCode(),
                                    "message", e.getMessage()
                            ))));
                    emitter.completeWithError(e);
                } catch (IOException ignored) {}
            } catch (Exception e) {
                log.error("Chat error: requestId={}", requestId, e);
                try {
                    emitter.send(SseEmitter.event()
                            .name("error")
                            .data(objectMapper.writeValueAsString(Map.of(
                                    "error", "ERR_UNKNOWN",
                                    "message", "Internal server error"
                            ))));
                    emitter.completeWithError(e);
                } catch (IOException ignored) {}
            }
            } finally {
                MDC.clear();
            }
        });

        return emitter;
    }

    private String truncate(String str, int maxLength) {
        if (str == null) return null;
        return str.length() > maxLength ? str.substring(0, maxLength) + "..." : str;
    }
}