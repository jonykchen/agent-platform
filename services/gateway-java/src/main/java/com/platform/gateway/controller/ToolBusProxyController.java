package com.platform.gateway.controller;

import com.platform.gateway.service.ToolBusClient;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.util.UriComponentsBuilder;
import reactor.core.publisher.Mono;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * Tool Bus API 代理控制器
 *
 * <p>将 /api/v1/internal/* 请求代理转发到 Tool Bus Java Service（端口 8083）。
 *
 * <h3>路由映射规则</h3>
 * <pre>
 *┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Gateway → Tool Bus 路由映射                        │
 * │                                                                             │
 * │  Gateway 路径                          Tool Bus Service 路径               │
 * │  ─────────────────────────────────────  ─────────────────────────────────  │
 * │  /api/v1/internal/tools/*          →    /internal/tools/*                  │
 * │                                                                             │
 * │  规则：去掉 /api/v1 前缀，保留 /internal/tools                              │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>API 端点列表</h3>
 * <table border="1">
 *   <tr>
 *     <th>方法</th><th>Gateway 路径</th><th>Tool Bus 路径</th><th>功能</th>
 *   </tr>
 *   <tr>
 *     <td>GET</td>
 *     <td>/api/v1/internal/tools</td>
 *     <td>/internal/tools</td>
 *     <td>列出所有工具</td>
 *   </tr>
 *   <tr>
 *     <td>GET</td>
 *     <td>/api/v1/internal/tools/{name}</td>
 *     <td>/internal/tools/{name}</td>
 *     <td>获取工具详情</td>
 *   </tr>
 *   <tr>
 *     <td>POST</td>
 *     <td>/api/v1/internal/tools/register</td>
 *     <td>/internal/tools/register</td>
 *     <td>注册新工具</td>
 *   </tr>
 *   <tr>
 *     <td>POST</td>
 *     <td>/api/v1/internal/tools/{name}/enable</td>
 *     <td>/internal/tools/{name}/enable</td>
 *     <td>启用工具</td>
 *   </tr>
 *   <tr>
 *     <td>POST</td>
 *     <td>/api/v1/internal/tools/{name}/disable</td>
 *     <td>/internal/tools/{name}/disable</td>
 *     <td>禁用工具</td>
 *   </tr>
 *   <tr>
 *     <td>DELETE</td>
 *     <td>/api/v1/internal/tools/{name}</td>
 *     <td>/internal/tools/{name}</td>
 *     <td>删除工具</td>
 *   </tr>
 *   <tr>
 *     <td>POST</td>
 *     <td>/api/v1/internal/tools/refresh</td>
 *     <td>/internal/tools/refresh</td>
 *     <td>刷新工具注册表</td>
 *   </tr>
 * </table>
 *
 * <h3>安全注意事项</h3>
 * <ul>
 *   <li>/internal/* 路径是内部管理接口，应限制为管理员访问</li>
 *   <li>生产环境需要配置访问控制</li>
 * </ul>
 *
 * @since 1.0.0
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/internal/tools")
@RequiredArgsConstructor
public class ToolBusProxyController {

    private final ToolBusClient toolBusClient;
    private final TenantContextService tenantContextService;

    // ─────────────────────────────────────────────────────────────────────────────
    // 工具管理 API
    // ─────────────────────────────────────────────────────────────────────────────

    /**
     * 列出所有工具
     *
     * @param category 可选的类别过滤
     * @param pageNumber 页码（前端使用 camelCase）
     * @param pageSize 每页数量（前端使用 camelCase）
     * @return 工具列表
     */
    @GetMapping
    public Mono<ResponseEntity<String>> listTools(
            @RequestParam(required = false) String category,
            @RequestParam(value = "pageNumber", required = false, defaultValue = "1") Integer pageNumber,
            @RequestParam(value = "pageSize", required = false, defaultValue = "10") Integer pageSize) {

        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[ToolBusProxy] List tools: requestId={}, category={}, pageNumber={}, pageSize={}",
                requestId, category, pageNumber, pageSize);

        // 前端传递 camelCase 参数，转换为 Tool Bus 期望的格式
        Map<String, String> queryParams = new HashMap<>();
        if (category != null && !category.isBlank()) {
            queryParams.put("category", category);
        }
        // Tool Bus 目前不支持分页，但保留参数兼容性
        queryParams.put("page", String.valueOf(pageNumber != null ? pageNumber : 1));
        queryParams.put("size", String.valueOf(pageSize != null ? pageSize : 10));

        return toolBusClient.proxyGet("/internal/tools", queryParams)
                .map(ResponseEntity::ok);
    }

    /**
     * 获取工具详情
     *
     * @param name 工具名称
     * @param version 版本号（可选）
     * @return 工具详情
     */
    @GetMapping("/{name}")
    public Mono<ResponseEntity<String>> getTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        String requestId = RequestIdGenerator.getCurrent();
        log.debug("[ToolBusProxy] Get tool: requestId={}, name={}, version={}",
                requestId, name, version);

        Map<String, String> queryParams = new HashMap<>();
        queryParams.put("version", version);

        // URL 编码路径参数，防止特殊字符导致的路由问题
        String encodedName = URLEncoder.encode(name, StandardCharsets.UTF_8);
        return toolBusClient.proxyGet("/internal/tools/" + encodedName, queryParams)
                .map(ResponseEntity::ok);
    }

    /**
     * 注册新工具
     *
     * @param body 工具注册请求（JSON）
     * @return 注册结果
     */
    @PostMapping("/register")
    public Mono<ResponseEntity<String>> registerTool(@RequestBody String body) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("[ToolBusProxy] Register tool: requestId={}", requestId);

        return toolBusClient.proxyPost("/internal/tools/register", body)
                .map(ResponseEntity::ok)
                .doOnSuccess(response -> log.info("[ToolBusProxy] Tool registered: requestId={}", requestId))
                .doOnError(e -> log.error("[ToolBusProxy] Register failed: requestId={}", requestId, e));
    }

    /**
     * 启用工具
     *
     * @param name 工具名称
     * @param version 版本号（可选）
     * @return 操作结果
     */
    @PostMapping("/{name}/enable")
    public Mono<ResponseEntity<String>> enableTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        String requestId = RequestIdGenerator.getCurrent();
        log.info("[ToolBusProxy] Enable tool: requestId={}, name={}, version={}",
                requestId, name, version);

        // URL 编码路径参数
        String encodedName = URLEncoder.encode(name, StandardCharsets.UTF_8);
        String encodedVersion = URLEncoder.encode(version, StandardCharsets.UTF_8);
        String path = UriComponentsBuilder.fromPath("/internal/tools/{name}/enable")
                .queryParam("version", encodedVersion)
                .buildAndExpand(encodedName)
                .toUriString();

        return toolBusClient.proxyPost(path)
                .map(ResponseEntity::ok)
                .doOnSuccess(response -> log.info("[ToolBusProxy] Tool enabled: requestId={}", requestId));
    }

    /**
     * 禁用工具
     *
     * @param name 工具名称
     * @param version 版本号（可选）
     * @return 操作结果
     */
    @PostMapping("/{name}/disable")
    public Mono<ResponseEntity<String>> disableTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        String requestId = RequestIdGenerator.getCurrent();
        log.info("[ToolBusProxy] Disable tool: requestId={}, name={}, version={}",
                requestId, name, version);

        // URL 编码路径参数
        String encodedName = URLEncoder.encode(name, StandardCharsets.UTF_8);
        String encodedVersion = URLEncoder.encode(version, StandardCharsets.UTF_8);
        String path = UriComponentsBuilder.fromPath("/internal/tools/{name}/disable")
                .queryParam("version", encodedVersion)
                .buildAndExpand(encodedName)
                .toUriString();

        return toolBusClient.proxyPost(path)
                .map(ResponseEntity::ok)
                .doOnSuccess(response -> log.info("[ToolBusProxy] Tool disabled: requestId={}", requestId));
    }

    /**
     * 删除工具
     *
     * @param name 工具名称
     * @param version 版本号（可选）
     * @return 删除结果
     */
    @DeleteMapping("/{name}")
    public Mono<ResponseEntity<String>> deleteTool(
            @PathVariable String name,
            @RequestParam(required = false, defaultValue = "1.0") String version) {

        String requestId = RequestIdGenerator.getCurrent();
        log.info("[ToolBusProxy] Delete tool: requestId={}, name={}, version={}",
                requestId, name, version);

        // URL 编码路径参数
        String encodedName = URLEncoder.encode(name, StandardCharsets.UTF_8);
        String encodedVersion = URLEncoder.encode(version, StandardCharsets.UTF_8);
        String path = UriComponentsBuilder.fromPath("/internal/tools/{name}")
                .queryParam("version", encodedVersion)
                .buildAndExpand(encodedName)
                .toUriString();

        return toolBusClient.proxyDelete(path)
                .map(ResponseEntity::ok)
                .doOnSuccess(response -> log.info("[ToolBusProxy] Tool deleted: requestId={}", requestId));
    }

    /**
     * 刷新工具注册表
     *
     * @return 刷新结果
     */
    @PostMapping("/refresh")
    public Mono<ResponseEntity<String>> refreshTools() {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("[ToolBusProxy] Refresh tools: requestId={}", requestId);

        return toolBusClient.proxyPost("/internal/tools/refresh")
                .map(ResponseEntity::ok)
                .doOnSuccess(response -> log.info("[ToolBusProxy] Tools refreshed: requestId={}", requestId));
    }
}
