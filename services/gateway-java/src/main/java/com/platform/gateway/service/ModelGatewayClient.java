package com.platform.gateway.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.dto.request.ChatRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

import jakarta.annotation.PostConstruct;
import java.time.Duration;
import java.util.HashMap;
import java.util.Map;

/**
 * Model Gateway 客户端
 *
 * <p>负责将请求透传到 Model Gateway 服务，支持 SSE (Server-Sent Events) 流式响应。
 *
 * <h3>架构位置</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          快速路径流程                                        │
 * │                                                                             │
 * │   用户请求                                                                  │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌─────────────┐                                                          │
 * │   │ FastPath    │  ───[风险扫描]───►  高风险？───► 拒绝快速路径            │
 * │   │ Service     │                                                          │
 * │   └─────────────┘                                                          │
 * │       │                                                                     │
 * │       ├──[简单问候]──► 预定义响应（延迟 &lt; 50ms）                          │
 * │       │                                                                     │
 * │       └──[需要模型]──► ModelGatewayClient.streamProxy()                    │
 * │                              │                                              │
 * │                              ▼                                              │
 * │                        ┌─────────────┐                                     │
 * │                        │ Model       │                                     │
 * │                        │ Gateway     │  http://localhost:8002              │
 * │                        │ (Python)    │                                     │
 * │                        └─────────────┘                                     │
 * │                              │                                              │
 * │                              ▼                                              │
 * │                        LLM Provider                                        │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>SSE 流式响应</h3>
 * <p>Model Gateway 返回 SSE 格式：
 * <pre>
 * data: {"content": "你好"}
 * data: {"content": "，我是"}
 * data: {"content": "AI 助手"}
 * data: [DONE]
 * </pre>
 *
 * <h3>连接配置</h3>
 * <ul>
 *   <li>连接超时: 10 秒</li>
 *   <li>读取超时: 60 秒</li>
 *   <li>最大内存: 16MB</li>
 * </ul>
 *
 * @since 1.0.0
 */
@Slf4j
@Service
public class ModelGatewayClient {

    @Value("${model-gateway.url:http://localhost:8002}")
    private String modelGatewayUrl;

    @Value("${model-gateway.connect-timeout:10}")
    private int connectTimeoutSeconds;

    @Value("${model-gateway.read-timeout:60}")
    private int readTimeoutSeconds;

    private WebClient webClient;
    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 初始化 WebClient
     */
    @PostConstruct
    public void init() {
        this.webClient = WebClient.builder()
                .baseUrl(modelGatewayUrl)
                .codecs(configurer -> configurer
                        .defaultCodecs()
                        .maxInMemorySize(16 * 1024 * 1024))  // 16MB
                .build();

        log.info("[ModelGatewayClient] Initialized with URL: {}", modelGatewayUrl);
    }

    /**
     * 流式透传请求到 Model Gateway
     *
     * <p>将 ChatRequest 转换为 Model Gateway 格式，并通过 SSE 流式返回响应。
     *
     * <h3>请求格式</h3>
     * <pre>{@code
     * {
     *   "messages": [
     *     {"role": "user", "content": "用户消息"}
     *   ],
     *   "model": "qwen-plus",
     *   "temperature": 0.7,
     *   "max_tokens": 2000,
     *   "stream": true
     * }
     * }</pre>
     *
     * <h3>响应格式</h3>
     * <p>返回 SSE 事件流，每个事件包含 JSON 格式的响应片段。
     *
     * @param request 对话请求
     * @return SSE 事件流
     */
    public Flux<ServerSentEvent<String>> streamProxy(ChatRequest request) {
        Map<String, Object> requestBody = buildRequestBody(request);

        log.debug("[ModelGatewayClient] Sending stream request to Model Gateway: {}", modelGatewayUrl);

        return webClient.post()
                .uri("/v1/chat/completions")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(requestBody)
                .retrieve()
                .bodyToFlux(String.class)
                .timeout(Duration.ofSeconds(readTimeoutSeconds))
                .map(this::parseToSSE)
                .onErrorMap(e -> {
                    log.error("[ModelGatewayClient] Stream proxy error: {}", e.getMessage());
                    return new RuntimeException("Model Gateway 调用失败: " + e.getMessage(), e);
                });
    }

    /**
     * 构建 Model Gateway 请求体
     *
     * @param request 原始对话请求
     * @return Model Gateway 格式的请求体
     */
    private Map<String, Object> buildRequestBody(ChatRequest request) {
        Map<String, Object> body = new HashMap<>();

        // 构建消息列表
        java.util.List<Map<String, String>> messages = new java.util.ArrayList<>();

        // 添加历史消息
        if (request.getHistory() != null && !request.getHistory().isEmpty()) {
            for (var history : request.getHistory()) {
                Map<String, String> msg = new HashMap<>();
                msg.put("role", history.getRole());
                msg.put("content", history.getContent());
                messages.add(msg);
            }
        }

        // 添加当前消息
        Map<String, String> currentMsg = new HashMap<>();
        currentMsg.put("role", "user");
        currentMsg.put("content", request.getMessage());
        messages.add(currentMsg);

        body.put("messages", messages);

        // 模型参数
        if (request.getModel() != null && !request.getModel().isBlank()) {
            body.put("model", request.getModel());
        } else {
            body.put("model", "qwen-plus");  // 默认模型
        }

        if (request.getTemperature() != null) {
            body.put("temperature", request.getTemperature());
        }

        if (request.getMaxTokens() != null) {
            body.put("max_tokens", request.getMaxTokens());
        }

        // 启用流式响应
        body.put("stream", true);

        return body;
    }

    /**
     * 将原始响应转换为 SSE 格式
     *
     * @param data 原始响应数据
     * @return SSE 事件
     */
    private ServerSentEvent<String> parseToSSE(String data) {
        return ServerSentEvent.<String>builder()
                .data(data)
                .build();
    }

    /**
     * 发送非流式请求到 Model Gateway
     *
     * <p>用于需要等待完整响应的场景。
     *
     * @param request 对话请求
     * @return 完整响应
     */
    public String sendRequest(ChatRequest request) {
        Map<String, Object> requestBody = buildRequestBody(request);
        requestBody.put("stream", false);  // 禁用流式

        log.debug("[ModelGatewayClient] Sending non-stream request to Model Gateway");

        return webClient.post()
                .uri("/v1/chat/completions")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(requestBody)
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(readTimeoutSeconds))
                .block();
    }
}