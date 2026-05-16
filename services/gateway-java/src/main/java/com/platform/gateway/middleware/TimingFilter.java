package com.platform.gateway.middleware;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

/**
 * 请求计时过滤器
 *
 * <p>统计所有 HTTP 请求的耗时，并输出到 Prometheus metrics。
 *
 * <h2>指标定义</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │  指标名称                        │ 类型   │ 标签                          │
 * ├─────────────────────────────────────────────────────────────────────────────┤
 * │  http_server_requests_seconds   │ Timer  │ method, uri, status, tenant  │
 * │  http_requests_total            │ Counter│ method, uri, status, tenant  │
 * │  http_active_requests           │ Gauge  │ tenant                        │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>Prometheus 查询示例</h2>
 * <pre>
 * # P95 响应时间（最近 5 分钟）
 * histogram_quantile(0.95,
 *   sum(rate(http_server_requests_seconds_bucket[5m])) by (le, uri)
 * )
 *
 * # 每秒请求数（QPS）
 * sum(rate(http_requests_total[1m])) by (tenant)
 *
 * # 错误率
 * sum(rate(http_requests_total{status=~"5.."}[5m])) /
 * sum(rate(http_requests_total[5m]))
 *
 * # 活跃请求数
 * http_active_requests
 * </pre>
 *
 * <h2>URI 模板化</h2>
 * <p>为避免高基数问题，URI 会被模板化：
 * <ul>
 *   <li>/api/v1/users/123 → /api/v1/users/{id}</li>
 *   <li>/api/v1/chat/sessions/abc-123 → /api/v1/chat/sessions/{id}</li>
 * </ul>
 *
 * <h2>Filter 顺序</h2>
 * <pre>
 * Request → RequestIdFilter(1) → TenantContextFilter(2) → LoggingFilter(3) → TimingFilter(4) → AuthFilter → Controller
 * </pre>
 *
 * @see io.micrometer.core.instrument.Timer
 * @see io.micrometer.core.instrument.Counter
 * @see io.micrometer.core.instrument.MeterRegistry
 */
@Slf4j
@Component
@Order(4)
public class TimingFilter implements Filter {

    private static final String START_TIME_ATTR = "timingStartTime";

    private final MeterRegistry meterRegistry;
    private final Counter.Builder requestCounterBuilder;
    private final Counter activeRequestsCounter;

    /**
     * 构造函数，初始化指标
     *
     * @param meterRegistry Micrometer MeterRegistry
     */
    public TimingFilter(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;

        // 请求计数器构建器
        this.requestCounterBuilder = Counter.builder("http.requests.total")
                .description("Total number of HTTP requests");

        // 活跃请求计数器
        this.activeRequestsCounter = Counter.builder("http.active.requests")
                .description("Number of active HTTP requests")
                .register(meterRegistry);
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        // 记录开始时间
        long startTime = System.nanoTime();
        httpRequest.setAttribute(START_TIME_ATTR, startTime);

        // 增加活跃请求计数
        activeRequestsCounter.increment();

        String tenantId = getTenantId(httpRequest);
        String uriTemplate = normalizeUri(httpRequest.getRequestURI());
        String method = httpRequest.getMethod();

        try {
            chain.doFilter(request, response);
        } finally {
            // 计算耗时
            long endTime = System.nanoTime();
            long durationNs = endTime - startTime;
            double durationSeconds = durationNs / 1_000_000_000.0;

            // 减少活跃请求计数
            activeRequestsCounter.increment(-1);

            // 记录指标
            recordMetrics(method, uriTemplate, httpResponse.getStatus(), tenantId, durationSeconds);

            // 记录慢请求日志（超过 1 秒）
            if (durationSeconds > 1.0) {
                log.warn("Slow request: method={}, uri={}, status={}, duration={}ms, tenant={}",
                        method, uriTemplate, httpResponse.getStatus(),
                        String.format("%.0f", durationSeconds * 1000), tenantId);
            }
        }
    }

    /**
     * 记录 Prometheus 指标
     *
     * @param method HTTP 方法
     * @param uri URI 模板
     * @param status HTTP 状态码
     * @param tenantId 租户 ID
     * @param durationSeconds 耗时（秒）
     */
    private void recordMetrics(String method, String uri, int status, String tenantId, double durationSeconds) {
        try {
            // 记录 Timer（响应时间分布）
            Timer.builder("http.server.requests.seconds")
                    .description("HTTP server request duration")
                    .tag("method", method)
                    .tag("uri", uri)
                    .tag("status", String.valueOf(status))
                    .tag("tenant", tenantId != null ? tenantId : "unknown")
                    .publishPercentiles(0.5, 0.9, 0.95, 0.99)
                    .publishPercentileHistogram()
                    .minimumExpectedValue(java.time.Duration.ofMillis(1))
                    .maximumExpectedValue(java.time.Duration.ofSeconds(30))
                    .register(meterRegistry)
                    .record((long) (durationSeconds * 1_000), TimeUnit.MILLISECONDS);

            // 记录 Counter（请求总数）
            requestCounterBuilder
                    .tag("method", method)
                    .tag("uri", uri)
                    .tag("status", String.valueOf(status))
                    .tag("tenant", tenantId != null ? tenantId : "unknown")
                    .register(meterRegistry)
                    .increment();

        } catch (Exception e) {
            log.warn("Failed to record metrics", e);
        }
    }

    /**
     * 获取租户 ID
     *
     * <p>从请求属性或 Header 中获取租户 ID。
     */
    private String getTenantId(HttpServletRequest request) {
        // 优先从 Header 获取
        String tenantId = request.getHeader("X-Tenant-ID");
        if (tenantId != null && !tenantId.isBlank()) {
            return tenantId;
        }

        // 尝试从请求属性获取
        Object tenantAttr = request.getAttribute("tenantId");
        if (tenantAttr instanceof String) {
            return (String) tenantAttr;
        }

        return null;
    }

    /**
     * 标准化 URI
     *
     * <p>将动态路径段替换为模板参数，避免高基数问题。
     *
     * <h3>示例</h3>
     * <ul>
     *   <li>/api/v1/users/123 → /api/v1/users/{id}</li>
     *   <li>/api/v1/chat/sessions/abc-123-456 → /api/v1/chat/sessions/{id}</li>
     *   <li>/api/v1/tenants/tenant_001/users/user_123 → /api/v1/tenants/{tenantId}/users/{userId}</li>
     * </ul>
     *
     * @param uri 原始 URI
     * @return 标准化后的 URI 模板
     */
    private String normalizeUri(String uri) {
        if (uri == null || uri.isEmpty()) {
            return "/";
        }

        // 移除查询参数
        int queryIndex = uri.indexOf('?');
        if (queryIndex >= 0) {
            uri = uri.substring(0, queryIndex);
        }

        // 分割路径段
        String[] segments = uri.split("/");
        StringBuilder normalized = new StringBuilder();

        for (int i = 0; i < segments.length; i++) {
            String segment = segments[i];
            if (segment.isEmpty()) {
                continue;
            }

            normalized.append("/");

            // 判断是否为动态段（UUID、数字等）
            if (isDynamicSegment(segment)) {
                // 根据位置推断参数名
                String paramName = inferParamName(normalized.toString(), i);
                normalized.append("{").append(paramName).append("}");
            } else {
                normalized.append(segment);
            }
        }

        return normalized.length() == 0 ? "/" : normalized.toString();
    }

    /**
     * 判断是否为动态路径段
     */
    private boolean isDynamicSegment(String segment) {
        // UUID 格式
        if (segment.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")) {
            return true;
        }

        // 纯数字
        if (segment.matches("\\d+")) {
            return true;
        }

        // 以 tenant_ 开头
        if (segment.startsWith("tenant_")) {
            return true;
        }

        // 以 user_ 开头
        if (segment.startsWith("user_")) {
            return true;
        }

        // 以 session_ 开头
        if (segment.startsWith("session_")) {
            return true;
        }

        // 以 req_ 开头
        if (segment.startsWith("req_")) {
            return true;
        }

        // 超过 20 字符的随机字符串
        if (segment.length() > 20 && segment.matches("[a-zA-Z0-9_-]+")) {
            return true;
        }

        return false;
    }

    /**
     * 推断参数名
     */
    private String inferParamName(String currentPath, int segmentIndex) {
        String path = currentPath.toLowerCase();

        if (path.endsWith("/users/")) {
            return "userId";
        }
        if (path.endsWith("/tenants/")) {
            return "tenantId";
        }
        if (path.endsWith("/sessions/")) {
            return "sessionId";
        }
        if (path.endsWith("/messages/")) {
            return "messageId";
        }
        if (path.endsWith("/agents/")) {
            return "agentId";
        }
        if (path.endsWith("/tools/")) {
            return "toolId";
        }
        if (path.endsWith("/approval/")) {
            return "approvalId";
        }

        return "id";
    }
}