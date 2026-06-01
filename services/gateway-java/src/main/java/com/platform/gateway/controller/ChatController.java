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
import java.util.concurrent.Executors;

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
    private final ExecutorService executor = Executors.newCachedThreadPool();

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

        executor.execute(() -> {
            try {
                ChatResponse response;

                // 快速路径判断：简单问答直接透传，不经过完整 Agent 编排
                if (fastPathService.isFastPath(request)) {
                    log.debug("Fast path detected for request {}", requestId);
                    response = fastPathService.handleFastPath(request);
                } else {
                    // 正常路径：调用 Orchestrator
                    response = orchestratorClient.sendChatRequest(request);
                }

                log.info("Chat response: requestId={}, model={}, tokens={}, latency={}ms",
                        requestId, response.getModelUsed(), response.getTotalTokens(), response.getLatencyMs());

                // 发送流式内容块
                emitter.send(SseEmitter.event()
                        .name("message")
                        .data(objectMapper.writeValueAsString(Map.of(
                                "delta_content", response.getResponse(),
                                "is_final", false
                        ))));

                // 发送最终块
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
        });

        return emitter;
    }

    private String truncate(String str, int maxLength) {
        if (str == null) return null;
        return str.length() > maxLength ? str.substring(0, maxLength) + "..." : str;
    }
}