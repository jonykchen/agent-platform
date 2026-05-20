package com.platform.gateway.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferUtils;
import org.springframework.core.io.buffer.DefaultDataBufferFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.http.codec.multipart.FilePart;
import org.springframework.http.codec.multipart.Part;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.BodyExtractors;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import jakarta.annotation.PostConstruct;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import java.util.function.Consumer;

/**
 * Knowledge Python Service 客户端
 *
 * <p>负责将 Knowledge API 请求代理转发到 Knowledge Python Service（端口 8003）。
 *
 * <h3>架构位置</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Knowledge API 代理流程                              │
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
 * │       │ /api/v1/knowledge/*                                                │
 * │       ▼                                                                     │
 * │   ┌─────────────────────────────────────────────┐                         │
 * │   │  KnowledgeProxyController                   │                          │
 * │   │  - 提取租户上下文 (TenantContextService)    │                          │
 * │   │  - 传递 Headers (X-Tenant-ID, X-Request-ID)│                          │
 * │   │  - 调用 KnowledgeClient                     │                          │
 * │   └─────────────────────────────────────────────┘                         │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌─────────────┐                                                          │
 * │   │ Knowledge   │                                                          │
 * │   │ (Python)    │                                                          │
 * │   │ Port:8003   │                                                          │
 * │   └─────────────┘                                                          │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   PostgreSQL + pgvector                                                     │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>API 端点映射</h3>
 * <table border="1">
 *   <tr><th>Gateway 路径</th><th>Knowledge Service 路径</th><th>说明</th></tr>
 *   <tr><td>/api/v1/knowledge/documents/upload</td><td>/api/v1/documents/upload</td><td>上传文档</td></tr>
 *   <tr><td>/api/v1/knowledge/documents/{id}</td><td>/api/v1/documents/{id}</td><td>获取/删除文档</td></tr>
 *   <tr><td>/api/v1/knowledge/documents</td><td>/api/v1/documents/</td><td>列出文档</td></tr>
 *   <tr><td>/api/v1/knowledge/search/query</td><td>/api/v1/search/query</td><td>检索知识库</td></tr>
 *   <tr><td>/api/v1/knowledge/search/similar/{id}</td><td>/api/v1/search/similar/{id}</td><td>相似内容</td></tr>
 * </table>
 *
 * <h3>请求头传递</h3>
 * <ul>
 *   <li>X-Tenant-ID: 租户隔离标识</li>
 *   <li>X-User-ID: 用户标识</li>
 *   <li>X-Request-ID: 请求追踪 ID</li>
 * </ul>
 *
 * <h3>超时配置</h3>
 * <ul>
 *   <li>连接超时: 10 秒</li>
 *   <li>读取超时: 60 秒（文档上传可能较长）</li>
 *   <li>最大内存: 50MB（支持大文件上传）</li>
 * </ul>
 *
 * @since 1.0.0
 */
@Slf4j
@Service
public class KnowledgeClient {

    @Value("${knowledge.url:http://localhost:8003}")
    private String knowledgeUrl;

    @Value("${knowledge.connect-timeout:10}")
    private int connectTimeoutSeconds;

    @Value("${knowledge.read-timeout:60}")
    private int readTimeoutSeconds;

    private WebClient webClient;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final TenantContextService tenantContextService;

    public KnowledgeClient(TenantContextService tenantContextService) {
        this.tenantContextService = tenantContextService;
    }

    /**
     * 初始化 WebClient
     */
    @PostConstruct
    public void init() {
        this.webClient = WebClient.builder()
                .baseUrl(knowledgeUrl)
                .codecs(configurer -> configurer
                        .defaultCodecs()
                        .maxInMemorySize(50 * 1024 * 1024))  // 50MB，支持文档上传
                .build();

        log.info("[KnowledgeClient] Initialized with URL: {}", knowledgeUrl);
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

            log.debug("[KnowledgeClient] Headers: tenant={}, user={}, request={}",
                    tenantId, userId, requestId);
        };
    }

    /**
     * 代理 GET 请求
     *
     * @param path 目标路径（不含前缀）
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
     * 代理 POST 请求（multipart 文件上传）
     *
     * <p>用于文档上传场景，将 FilePart 转换为 multipart/form-data 格式。
     *
     * @param path 目标路径
     * @param filePart 上传的文件
     * @return 响应 JSON 字符串
     */
    public Mono<String> proxyMultipartPost(String path, FilePart filePart) {
        return webClient.post()
                .uri(path)
                .headers(buildHeaders())
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(Mono.just(filePart), FilePart.class)
                .retrieve()
                .bodyToMono(String.class)
                .timeout(Duration.ofSeconds(readTimeoutSeconds * 2))  // 文件上传需要更长超时
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
            log.error("[KnowledgeClient] HTTP error: requestId={}, status={}, body={}",
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
                    "Knowledge 服务暂时不可用");
            }

            return new BusinessException(ErrorCode.ERR_UNKNOWN,
                "Knowledge 服务调用失败: " + wce.getMessage());
        }

        log.error("[KnowledgeClient] Unexpected error: requestId={}", requestId, error);
        return new BusinessException(ErrorCode.ERR_SERVICE_UNAVAILABLE,
            "Knowledge 服务调用失败: " + error.getMessage());
    }

    /**
     * 从错误响应中提取错误消息
     */
    private String extractErrorMessage(String responseBody) {
        try {
            Map<String, Object> errorMap = objectMapper.readValue(responseBody, Map.class);
            if (errorMap.containsKey("detail")) {
                Object detail = errorMap.get("detail");
                if (detail instanceof String) {
                    return (String) detail;
                }
                if (detail instanceof Map) {
                    Map<?, ?> detailMap = (Map<?, ?>) detail;
                    if (detailMap.containsKey("message")) {
                        return String.valueOf(detailMap.get("message"));
                    }
                }
            }
            if (errorMap.containsKey("message")) {
                return String.valueOf(errorMap.get("message"));
            }
        } catch (Exception e) {
            log.debug("[KnowledgeClient] Failed to parse error response: {}", e.getMessage());
        }
        return responseBody;
    }
}