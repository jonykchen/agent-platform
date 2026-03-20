package com.platform.gateway.controller;

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
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 对话控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/chat")
@RequiredArgsConstructor
public class ChatController {

    private final FastPathService fastPathService;
    private final OrchestratorClient orchestratorClient;
    private final TenantContextService tenantContextService;

    /**
     * 对话补全接口
     */
    @PostMapping("/completions")
    public ResponseEntity<ChatResponse> chatCompletion(@Valid @RequestBody ChatRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        log.info("Chat request: requestId={}, tenant={}, user={}, message={}",
                requestId, tenantId, userId, truncate(request.getMessage(), 100));

        try {
            // 快速路径判断：简单问答直接透传，不经过完整 Agent 编排
            if (fastPathService.isFastPath(request.getMessage())) {
                log.debug("Fast path detected for request {}", requestId);
                return ResponseEntity.ok(fastPathService.handleFastPath(request));
            }

            // 正常路径：调用 Orchestrator
            ChatResponse response = orchestratorClient.sendChatRequest(request);

            log.info("Chat response: requestId={}, model={}, tokens={}, latency={}ms",
                    requestId, response.getModelUsed(), response.getTotalTokens(), response.getLatencyMs());

            return ResponseEntity.ok(response);

        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Chat error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Service temporarily unavailable");
        }
    }

    private String truncate(String str, int maxLength) {
        if (str == null) return null;
        return str.length() > maxLength ? str.substring(0, maxLength) + "..." : str;
    }
}