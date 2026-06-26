package com.platform.gateway.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Mono;

import jakarta.annotation.PostConstruct;
import java.time.Duration;
import java.util.Map;
import java.util.function.Consumer;

/**
 * Tool Bus Java Service 客户端
 *
 * <p>负责将 Tool Bus API 请求代理转发到 Tool Bus Service（端口 8083）。
 *
 * <h3>架构位置</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Tool Bus API 代理流程                               │
 * │                                                                             │
 * │   前端请求                                                                   │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌─────────────┐                                                          │
 * │   │ Gateway     │                                                          │
 * │   │ (Java)      │                                                          │
 * │   │ Port:8080   │                                                          │
 * │   └─────────────┘                                                          │
 * │       │                                                                     │
 * │       │ /api/v1/internal/*                                                 │
 * │       ▼                                                                     │
 * │   ┌─────────────────────────────────────────────┐                         │
 * │   │  ToolBusProxyController                     │                          │
 * │   │  - 提取租户上下文 (TenantContextService)    │                          │
 * │   │  - 传递 Headers (X-Tenant-ID, X-Request-ID)│                          │
 * │   │  - 调用 ToolBusClient                       │                          │
 * │   └─────────────────────────────────────────────┘                         │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌─────────────┐                                                          │
 * │   │ Tool Bus    │                                                          │
 * │   │ (Java)      │                                                          │
 * │   │ Port:8083   │                                                          │
 * │   └─────────────┘                                                          │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   PostgreSQL                                                                 │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>API 端点映射</h3>
 * <table border="1">
 *   <tr><th>Gateway 路径</th><th>Tool Bus Service 路径</th><th>说明</th></tr>
 *   <tr><td>/api/v1/internal/tools</td><td>/internal/tools</td><td>列出工具</td></tr>
 *   <tr><td>/api/v1/internal/tools/{name}</td><td>/internal/tools/{name}</td><td>获取工具详情</td></tr>
 *   <tr><td>/api/v1/internal/tools/register</td><td>/internal/tools/register</td><td>注册工具</td></tr>
 *   <tr><td>/api/v1/internal/tools/{name}/enable</td><td>/internal/tools/{name}/enable</td><td>启用工具</td></tr>
 *   <tr><td>/api/v1/internal/tools/{name}/disable</td><td>/internal/tools/{name}/disable</td><td>禁用工具</td></tr>
 * </table>
 *
 * @since 1.0.0
 */
@Slf4j
@Service
public class ToolBusClient {

    @Value("${tool-bus.url:http://localhost:8083}")
    private String toolBusUrl;

    @Value("${tool-bus.connect-timeout:10}")
    private int connectTimeoutSeconds;

    @Value("${tool-bus.read-timeout:30}")
    private int readTimeoutSeconds;

    private WebClient webClient;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final TenantContextService tenantContextService;

    public ToolBusClient(TenantContextService tenantContextService) {
        this.tenantContextService = tenantContextService;
    }

    /**
     * 初始化 WebClient
     */
    @PostConstruct
    public void init() {
        this.webClient = WebClient.builder()
                .baseUrl(toolBusUrl)
                .codecs(configurer -> configurer
                        .defaultCodecs()
                        .maxInMemorySize(10 * 1024 * 1024))  // 10MB
                .build();

        log.info("[ToolBusClient] Initialized with URL: {}", toolBusUrl);
    }

    /**
     * 构建带租户上下文的请求 Headers
     *
     * @return HttpHeaders Consumer
     */
    private Consumer<HttpHeaders> buildHeaders() {
        return headers -> {
            String tenantId = tenantContextService.getCurrentTenantId();
            String userId = tenantContextService.getCurrentUserId();
            String requestId = RequestIdGenerator.getCurrent();

            if (tenantId != null) {
                headers.add("X-Tenant-ID", tenantId);
            }
            if (userId != null) {
                headers.add("X-User-ID", userId);
            }
            if (requestId != null) {
                headers.add("X-Request-ID", requestId);
            }

            // 内部服务调用标识（Tool Bus ServiceRoleAuthenticationFilter 需要）
            headers.add("X-Service-Role", "ADMIN");

            log.debug("[ToolBusClient] Headers: tenant={}, user={}, request={}",
                    tenantId, userId, requestId);
        };
    }

    /**
     * 代理 GET 请求
     *
     * @param path 目标路径
     * @param queryParams 查询参数
     * @return 响应 JSON 字符串
     */
    public Mono<String> proxyGet(String path, Map<String, String> queryParams) {
        WebClient.RequestHeadersSpec<?> request = webClient.get()
                .uri(uriBuilder -> {
                    uriBuilder.path(path);
                    if (queryParams != null) {
                        queryParams.forEach(uriBuilder::queryParam);
                    }
                    return uriBuilder.build();
                })
                .headers(buildHeaders());

        return request.retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(readTimeoutSeconds))
                .onErrorMap(this::handleError);
    }

    /**
     * 代理 POST 请求（JSON Body）
     *
     * @param path 目标路径
     * @param body JSON 请求体
     * @return 响应 JSON 字符串
     */
    public Mono<String> proxyPost(String path, String body) {
        return webClient.post()
                .uri(path)
                .headers(buildHeaders())
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body)
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(readTimeoutSeconds))
                .onErrorMap(this::handleError);
    }

    /**
     * 代理 POST 请求（无 Body）
     *
     * @param path 目标路径
     * @return 响应 JSON 字符串
     */
    public Mono<String> proxyPost(String path) {
        return webClient.post()
                .uri(path)
                .headers(buildHeaders())
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(readTimeoutSeconds))
                .onErrorMap(this::handleError);
    }

    /**
     * 代理 DELETE 请求
     *
     * @param path 目标路径
     * @return 响应 JSON 字符串
     */
    public Mono<String> proxyDelete(String path) {
        return webClient.delete()
                .uri(path)
                .headers(buildHeaders())
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(readTimeoutSeconds))
                .onErrorMap(this::handleError);
    }

    /**
     * 处理 WebClient 错误
     *
     * @param error 原始错误
     * @return 业务异常
     */
    private Throwable handleError(Throwable error) {
        String requestId = RequestIdGenerator.getCurrent();

        if (error instanceof WebClientResponseException) {
            WebClientResponseException wce = (WebClientResponseException) error;
            log.error("[ToolBusClient] HTTP error: requestId={}, status={}, body={}",
                    requestId, wce.getStatusCode(), wce.getResponseBodyAsString());

            // 根据状态码映射错误
            if (wce.getStatusCode().value() == 404) {
                return new BusinessException(ErrorCode.ERR_NOT_FOUND, "资源不存在");
            }
            if (wce.getStatusCode().value() == 400) {
                return new BusinessException(ErrorCode.ERR_INVALID_REQUEST,
                    "请求参数错误: " + extractErrorMessage(wce.getResponseBodyAsString()));
            }
            if (wce.getStatusCode().value() >= 500) {
                return new BusinessException(ErrorCode.ERR_SERVICE_UNAVAILABLE,
                    "Tool Bus 服务暂时不可用");
            }

            return new BusinessException(ErrorCode.ERR_UNKNOWN,
                "Tool Bus 服务调用失败: " + wce.getMessage());
        }

        log.error("[ToolBusClient] Unexpected error: requestId={}", requestId, error);
        return new BusinessException(ErrorCode.ERR_SERVICE_UNAVAILABLE,
            "Tool Bus 服务调用失败: " + error.getMessage());
    }

    /**
     * 从错误响应中提取错误消息
     */
    private String extractErrorMessage(String responseBody) {
        try {
            Map<String, Object> errorMap = objectMapper.readValue(responseBody, Map.class);
            if (errorMap.containsKey("message")) {
                return String.valueOf(errorMap.get("message"));
            }
            if (errorMap.containsKey("error")) {
                return String.valueOf(errorMap.get("error"));
            }
        } catch (Exception e) {
            log.debug("[ToolBusClient] Failed to parse error response: {}", e.getMessage());
        }
        return responseBody;
    }
}
