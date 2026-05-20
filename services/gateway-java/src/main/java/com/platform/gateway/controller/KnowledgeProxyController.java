package com.platform.gateway.controller;

import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.KnowledgeClient;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
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
 * <h3>API 端点列表</h3>
 * <table border="1">
 *   <tr>
 *     <th>方法</th><th>Gateway 路径</th><th>Knowledge 路径</th><th>功能</th>
 *   </tr>
 *   <tr>
 *     <td>POST</td>
 *     <td>/api/v1/knowledge/documents/upload</td>
 *     <td>/api/v1/documents/upload</td>
 *     <td>上传文档（multipart）</td>
 *   </tr>
 *   <tr>
 *     <td>GET</td>
 *     <td>/api/v1/knowledge/documents/{id}</td>
 *     <td>/api/v1/documents/{id}</td>
 *     <td>获取文档信息</td>
 *   </tr>
 *   <tr>
 *     <td>DELETE</td>
 *     <td>/api/v1/knowledge/documents/{id}</td>
 *     <td>/api/v1/documents/{id}</td>
 *     <td>删除文档</td>
 *   </tr>
 *   <tr>
 *     <td>GET</td>
 *     <td>/api/v1/knowledge/documents</td>
 *     <td>/api/v1/documents/</td>
 *     <td>列出文档列表</td>
 *   </tr>
 *   <tr>
 *     <td>POST</td>
 *     <td>/api/v1/knowledge/search/query</td>
 *     <td>/api/v1/search/query</td>
 *     <td>检索知识库</td>
 *   </tr>
 *   <tr>
 *     <td>POST</td>
 *     <td>/api/v1/knowledge/search/similar/{id}</td>
 *     <td>/api/v1/search/similar/{id}</td>
 *     <td>相似内容查找</td>
 *   </tr>
 * </table>
 *
 * <h3>请求头传递</h3>
 * <ul>
 *   <li>X-Tenant-ID: 租户隔离标识（必需）</li>
 *   <li>X-User-ID: 用户标识（可选）</li>
 *   <li>X-Request-ID: 请求追踪 ID（自动生成）</li>
 * </ul>
 *
 * <h3>安全注意事项</h3>
 * <ul>
 *   <li>所有请求必须携带有效的租户 ID（由 TenantContextFilter 验证）</li>
 *   <li>文件上传限制：50MB（由 Knowledge Service 实际限制）</li>
 *   <li>支持的文档格式：pdf, docx, doc, txt, md</li>
 * </ul>
 *
 * <h3>错误处理</h3>
 * <ul>
 *   <li>400: 请求参数错误（如不支持的文件格式）</li>
 *   <li>404: 文档不存在</li>
 *   <li>500: Knowledge 服务内部错误</li>
 *   <li>503: Knowledge 服务不可用</li>
 * </ul>
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
     *
     * <p>接收 multipart/form-data 格式的文件上传请求，转发到 Knowledge Service。
     *
     * <h3>请求示例</h3>
     * <pre>{@code
     * curl -X POST http://localhost:8080/api/v1/knowledge/documents/upload \
     *   -H "X-Tenant-ID: tenant_001" \
     *   -F "file=@document.pdf"
     * }</pre>
     *
     * <h3>响应示例</h3>
     * <pre>{@code
     * {
     *   "document_id": "abc123",
     *   "name": "document.pdf",
     *   "status": "ready",
     *   "message": "文档处理完成，共 15 个片段"
     * }
     * }</pre>
     *
     * @param filePart 上传的文件
     * @return 上传结果
     */
    @PostMapping(value = "/documents/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Mono<ResponseEntity<String>> uploadDocument(@RequestPart("file") FilePart filePart) {
        String requestId = RequestIdGenerator.getCurrent();
        String tenantId = tenantContextService.getCurrentTenantId();

        log.info("[KnowledgeProxy] Upload request: requestId={}, tenant={}, filename={}",
                requestId, tenantId, filePart.filename());

        return knowledgeClient.proxyMultipartPost("/api/v1/documents/upload", filePart)
                .map(ResponseEntity::ok)
                .doOnSuccess(response -> log.info("[KnowledgeProxy] Upload completed: requestId={}", requestId))
                .doOnError(e -> log.error("[KnowledgeProxy] Upload failed: requestId={}", requestId, e));
    }

    /**
     * 获取文档信息
     *
     * @param documentId 文档 ID
     * @return 文档信息
     */
    @GetMapping("/documents/{documentId}")
    public Mono<ResponseEntity<String>> getDocument(@PathVariable String documentId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] Get document: requestId={}, documentId={}", requestId, documentId);

        return knowledgeClient.proxyGet("/api/v1/documents/" + documentId, null)
                .map(ResponseEntity::ok);
    }

    /**
     * 删除文档
     *
     * @param documentId 文档 ID
     * @return 删除结果
     */
    @DeleteMapping("/documents/{documentId}")
    public Mono<ResponseEntity<String>> deleteDocument(@PathVariable String documentId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("[KnowledgeProxy] Delete document: requestId={}, documentId={}", requestId, documentId);

        return knowledgeClient.proxyDelete("/api/v1/documents/" + documentId)
                .map(ResponseEntity::ok)
                .doOnSuccess(response -> log.info("[KnowledgeProxy] Delete completed: requestId={}", requestId));
    }

    /**
     * 列出文档列表
     *
     * @param status 状态筛选（可选）
     * @param limit 返回数量（默认 20）
     * @param offset 偏移量（默认 0）
     * @return 文档列表
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
                .map(ResponseEntity::ok);
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // 检索 API
    // ─────────────────────────────────────────────────────────────────────────────

    /**
     * 检索知识库
     *
     * <p>核心检索接口，支持向量检索和混合检索。
     *
     * <h3>请求体示例</h3>
     * <pre>{@code
     * {
     *   "query": "如何配置 API Key",
     *   "top_k": 10,
     *   "filters": {
     *     "document_ids": ["doc_001", "doc_002"]
     *   },
     *   "use_hybrid": true,
     *   "alpha": 0.7
     * }
     * }</pre>
     *
     * <h3>响应示例</h3>
     * <pre>{@code
     * {
     *   "results": [
     *     {
     *       "chunk_id": "chunk_001",
     *       "document_id": "doc_001",
     *       "document_name": "配置手册.pdf",
     *       "content": "API Key 配置步骤...",
     *       "score": 0.89,
     *       "metadata": {"page": 5},
     *       "source": "hybrid"
     *     }
     *   ],
     *   "total": 10,
     *   "query": "如何配置 API Key",
     *   "latency_ms": 85
     * }
     * }</pre>
     *
     * @param body JSON 请求体
     * @return 检索结果
     */
    @PostMapping("/search/query")
    public Mono<ResponseEntity<String>> searchKnowledge(@RequestBody String body) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] Search request: requestId={}", requestId);

        return knowledgeClient.proxyPost("/api/v1/search/query", body)
                .map(ResponseEntity::ok);
    }

    /**
     * 查找相似内容
     *
     * <p>基于指定的 chunk 查找相似内容，用于推荐场景。
     *
     * @param chunkId 块 ID
     * @param topK 返回数量（默认 10）
     * @return 相似内容列表
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
                .map(ResponseEntity::ok);
    }

    // ─────────────────────────────────────────────────────────────────────────────
    // 统计 API（扩展）
    // ─────────────────────────────────────────────────────────────────────────────

    /**
     * 获取知识库统计信息
     *
     * <p>返回当前租户的知识库统计数据，包括文档数量、总 chunk 数等。
     *
     * @return 统计信息
     */
    @GetMapping("/stats")
    public Mono<ResponseEntity<String>> getStats() {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[KnowledgeProxy] Get stats: requestId={}", requestId);

        // 如果 Knowledge Service 未提供 /stats 端点，则返回默认值
        // return knowledgeClient.proxyGet("/api/v1/stats", null).map(ResponseEntity::ok);

        // 暂时返回模拟数据
        String mockStats = """
            {
              "document_count": 0,
              "chunk_count": 0,
              "storage_mb": 0.0,
              "last_updated": null
            }
            """;
        return Mono.just(ResponseEntity.ok(mockStats));
    }
}
