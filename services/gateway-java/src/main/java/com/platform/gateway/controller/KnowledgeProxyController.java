package com.platform.gateway.controller;

import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.KnowledgeClient;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.codec.multipart.FilePart;
import org.springframework.web.bind.annotation.*;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

/**
 * Knowledge API 代理控制器
 *
 * <p>将 /api/v1/knowledge/* 请求代理转发到 Knowledge Python Service（端口 8003）。
 *
 * <h3>路由映射规则</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Gateway → Knowledge 路由映射                       │
 * │                                                                             │
 * │  Gateway 路径                      Knowledge Service 路径                   │
 * │  ────────────────────────────────  ──────────────────────────────────────  │
 * │  /api/v1/knowledge/documents/*    →  /api/v1/documents/*                  │
 * │  /api/v1/knowledge/search/*       →  /api/v1/search/*                     │
 * │                                                                             │
 * │  规则：去掉 /api/v1/knowledge 前缀，替换为 /api/v1                           │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>异步错误处理</h3>
 * <p>Controller 返回 Mono，如果下游服务返回错误（如 404、500），
 * KnowledgeClient 会将 WebClientResponseException 转换为 BusinessException。
 * 由于 Servlet + Reactor 混合架构下，Mono 的异步异常无法被 @RestControllerAdvice
 * 正确捕获（会被 Spring Security 的 ExceptionTranslationFilter 拦截为 403），
 * 因此每个端点使用 .onErrorResume() 在 Mono 层面处理错误，直接返回正确的 HTTP 响应。
 *
 * @since 1.0.0
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/knowledge")
@RequiredArgsConstructor
public class KnowledgeProxyController {

    private final KnowledgeClient knowledgeClient;
    private final TenantContextService tenantContextService;

    // ─────────────────────────────────────────────────────────────────────────────
    // 文档管理 API
    // ─────────────────────────────────────────────────────────────────────────────

    /**
     * 上传文档
     */
    @PostMapping(value = "/documents/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Mono<ResponseEntity<String>> uploadDocument(@RequestPart("file") FilePart filePart) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("[KnowledgeProxy] Upload request: requestId={}, tenant={}, filename={}",
                requestId, tenantId, filePart.filename());

        return knowledgeClient.proxyMultipartPost("/api/v1/documents/upload", filePart)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> handleProxyError(e, "Upload"))
                .doOnSuccess(response -> log.info("[KnowledgeProxy] Upload completed: requestId={}", requestId));
    }

    /**
     * 获取文档信息
     */
    @GetMapping("/documents/{documentId}")
    public Mono<ResponseEntity<String>> getDocument(@PathVariable String documentId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] Get document: requestId={}, documentId={}", requestId, documentId);

        return knowledgeClient.proxyGet("/api/v1/documents/" + documentId, null)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> handleProxyError(e, "GetDocument"));
    }

    /**
     * 删除文档
     */
    @DeleteMapping("/documents/{documentId}")
    public Mono<ResponseEntity<String>> deleteDocument(@PathVariable String documentId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("[KnowledgeProxy] Delete document: requestId={}, documentId={}", requestId, documentId);

        return knowledgeClient.proxyDelete("/api/v1/documents/" + documentId)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> handleProxyError(e, "Delete"))
                .doOnSuccess(response -> log.info("[KnowledgeProxy] Delete completed: requestId={}", requestId));
    }

    /**
     * 列出文档列表
     */
    @GetMapping("/documents")
    public Mono<ResponseEntity<String>> listDocuments(
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "20") int limit,
            @RequestParam(defaultValue = "0") int offset) {

        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] List documents: requestId={}, status={}, limit={}, offset={}",
                requestId, status, limit, offset);

        Map<String, String> queryParams = new HashMap<>();
        if (status != null) {
            queryParams.put("status", status);
        }
        queryParams.put("limit", String.valueOf(limit));
        queryParams.put("offset", String.valueOf(offset));

        return knowledgeClient.proxyGet("/api/v1/documents/", queryParams)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> handleProxyError(e, "ListDocuments"));
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // 检索 API
    // ─────────────────────────────────────────────────────────────────────────────

    /**
     * 检索知识库
     */
    @PostMapping("/search/query")
    public Mono<ResponseEntity<String>> searchKnowledge(@RequestBody String body) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] Search request: requestId={}", requestId);

        return knowledgeClient.proxyPost("/api/v1/search/query", body)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> handleProxyError(e, "Search"));
    }

    /**
     * 查找相似内容
     */
    @PostMapping("/search/similar/{chunkId}")
    public Mono<ResponseEntity<String>> findSimilar(
            @PathVariable String chunkId,
            @RequestParam(defaultValue = "10") int topK) {

        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] Find similar: requestId={}, chunkId={}, topK={}",
                requestId, chunkId, topK);

        Map<String, String> queryParams = new HashMap<>();
        queryParams.put("top_k", String.valueOf(topK));

        return knowledgeClient.proxyGet("/api/v1/search/similar/" + chunkId, queryParams)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> handleProxyError(e, "FindSimilar"));
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // 统计 API
    // ─────────────────────────────────────────────────────────────────────────────

    /**
     * 获取知识库统计信息
     */
    @GetMapping("/stats")
    public Mono<ResponseEntity<String>> getStats() {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] Get stats: requestId={}", requestId);

        return knowledgeClient.proxyGet("/api/v1/stats", null)
                .map(ResponseEntity::ok)
                .onErrorResume(e -> handleProxyError(e, "GetStats"));
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // 统一错误处理
    // ─────────────────────────────────────────────────────────────────────────────

    /**
     * 统一处理代理请求的错误。
     *
     * <p>在 Servlet + Reactor 混合架构下，Mono 的异步异常无法被 @RestControllerAdvice
     * 正确捕获，会被 Spring Security 的 ExceptionTranslationFilter 拦截为 403。
     * 因此在 Mono 层面用 onErrorResume 将错误转为正确的 HTTP 响应。
     *
     * @param error 异常实例
     * @param operation 操作名称（用于日志）
     * @return 错误响应的 Mono
     */
    private Mono<ResponseEntity<String>> handleProxyError(Throwable error, String operation) {
        if (error instanceof BusinessException biz) {
            log.warn("[KnowledgeProxy] {} failed: code={}, msg={}", operation, biz.getErrorCode().getCode(), biz.getMessage());
            int status = biz.getErrorCode().getHttpStatus();
            String body = String.format(
                    "{\"error\":\"%s\",\"message\":\"%s\"}",
                    biz.getErrorCode().getCode(),
                    biz.getMessage()
            );
            return Mono.just(ResponseEntity.status(status).body(body));
        }

        log.error("[KnowledgeProxy] {} failed with unexpected error", operation, error);
        String body = String.format(
                "{\"error\":\"ERR_SERVICE_UNAVAILABLE\",\"message\":\"Knowledge 服务暂时不可用: %s\"}",
                error.getMessage()
        );
        return Mono.just(ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(body));
    }
}
