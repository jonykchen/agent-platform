package com.platform.gateway.middleware;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.util.Enumeration;
import java.util.HashMap;
import java.util.Map;

/**
 * 日志过滤器
 *
 * <p>记录所有 HTTP 请求的访问日志，包含完整的请求/响应信息。
 *
 * <h2>日志字段</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │  字段名          │ 说明                      │ 示例                       │
 * ├─────────────────────────────────────────────────────────────────────────────┤
 * │  timestamp       │ ISO 8601 时间戳           │ 2024-01-15T10:30:00.123Z  │
 * │  request_id      │ 全链路追踪 ID             │ req_abc123                 │
 * │  tenant_id       │ 租户 ID                   │ tenant_001                 │
 * │  user_id         │ 用户 ID                   │ user_123                   │
 * │  method          │ HTTP 方法                 │ POST                       │
 * │  path            │ 请求路径                  │ /api/v1/chat               │
 * │  query           │ 查询参数                  │ ?model=gpt-4              │
 * │  status          │ HTTP 状态码               │ 200                        │
 * │  duration_ms     │ 请求耗时（毫秒）          │ 1234                       │
 * │  client_ip       │ 客户端 IP                 │ 192.168.1.100              │
 * │  user_agent      │ 用户代理                  │ Mozilla/5.0...            │
 * │  request_size    │ 请求体大小（字节）         │ 1024                       │
 * │  response_size   │ 响应体大小（字节）         │ 2048                       │
 * │  error           │ 错误信息（如有）          │ Invalid request            │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>敏感数据脱敏</h2>
 * <p>以下字段自动脱敏：
 * <ul>
 *   <li>Authorization Header: Bearer ***...</li>
 *   <li>X-API-Key Header: ***...</li>
 *   <li>Password 字段: ***</li>
 *   <li>Token 字段: ***</li>
 * </ul>
 *
 * <h2>日志级别</h2>
 * <ul>
 *   <li>INFO: 正常请求（2xx, 3xx）</li>
 *   <li>WARN: 客户端错误（4xx）</li>
 *   <li>ERROR: 服务端错误（5xx）</li>
 * </ul>
 *
 * <h2>Filter 顺序</h2>
 * <pre>
 * Request → RequestIdFilter(1) → TenantContextFilter(2) → LoggingFilter(3) → AuthFilter → Controller
 * </pre>
 *
 * @see RequestIdFilter
 * @see TenantContextFilter
 */
@Slf4j
@Component
@Order(3)
@RequiredArgsConstructor
public class LoggingFilter implements Filter {

    private static final String START_TIME_ATTR = "startTime";
    private static final String REQUEST_SIZE_ATTR = "requestSize";

    private final TenantContextService tenantContextService;
    private final ObjectMapper objectMapper;

    /**
     * 需要脱敏的 Header 名称
     */
    private static final java.util.Set<String> SENSITIVE_HEADERS = java.util.Set.of(
            "authorization",
            "x-api-key",
            "x-auth-token",
            "cookie",
            "set-cookie"
    );

    /**
     * 需要脱敏的请求体字段
     */
    private static final java.util.Set<String> SENSITIVE_FIELDS = java.util.Set.of(
            "password",
            "token",
            "secret",
            "api_key",
            "apiKey",
            "access_token",
            "refresh_token",
            "credential"
    );

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        // 记录请求开始时间
        long startTime = System.currentTimeMillis();
        httpRequest.setAttribute(START_TIME_ATTR, startTime);

        // 记录请求大小
        int requestSize = httpRequest.getContentLength();
        httpRequest.setAttribute(REQUEST_SIZE_ATTR, requestSize);

        try {
            chain.doFilter(request, response);
        } finally {
            // 计算耗时
            long duration = System.currentTimeMillis() - startTime;

            // 记录访问日志（不再包装 response，避免干扰 Mono/Flux 异步写入）
            logAccess(httpRequest, httpResponse, duration, requestSize);
        }
    }

    /**
     * 记录访问日志
     *
     * @param request HTTP 请求
     * @param response HTTP 响应
     * @param durationMs 耗时（毫秒）
     * @param requestSize 请求大小
     */
    private void logAccess(HttpServletRequest request, HttpServletResponse response,
                          long durationMs, int requestSize) {
        try {
            Map<String, Object> accessLog = buildAccessLog(request, response, durationMs, requestSize);
            String logJson = objectMapper.writeValueAsString(accessLog);

            int status = response.getStatus();
            if (status >= 500) {
                log.error("HTTP Access: {}", logJson);
            } else if (status >= 400) {
                log.warn("HTTP Access: {}", logJson);
            } else {
                log.info("HTTP Access: {}", logJson);
            }
        } catch (Exception e) {
            log.warn("Failed to write access log", e);
        }
    }

    /**
     * 构建访问日志对象
     */
    private Map<String, Object> buildAccessLog(HttpServletRequest request, HttpServletResponse response,
                                               long durationMs, int requestSize) {
        Map<String, Object> log = new HashMap<>();

        // 基础信息
        log.put("timestamp", Instant.now().toString());
        log.put("request_id", MDC.get("request_id"));
        log.put("tenant_id", tenantContextService.getCurrentTenantId());
        log.put("user_id", tenantContextService.getCurrentUserId());

        // 请求信息
        log.put("method", request.getMethod());
        log.put("path", request.getRequestURI());
        log.put("query", request.getQueryString());
        log.put("client_ip", getClientIp(request));
        log.put("user_agent", request.getHeader("User-Agent"));

        // 响应信息
        log.put("status", response.getStatus());
        log.put("duration_ms", durationMs);
        log.put("request_size", requestSize);
        log.put("response_size", -1);  // 不再包装 response，无法获取精确响应大小

        // 请求头（脱敏）
        log.put("headers", sanitizeHeaders(request));

        return log;
    }

    /**
     * 获取客户端真实 IP
     *
     * <p>支持通过代理的情况，从 X-Forwarded-For 或 X-Real-IP 获取。
     */
    private String getClientIp(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isBlank()) {
            return xForwardedFor.split(",")[0].trim();
        }

        String xRealIp = request.getHeader("X-Real-IP");
        if (xRealIp != null && !xRealIp.isBlank()) {
            return xRealIp;
        }

        return request.getRemoteAddr();
    }

    /**
     * 脱敏请求头
     */
    private Map<String, String> sanitizeHeaders(HttpServletRequest request) {
        Map<String, String> headers = new HashMap<>();
        Enumeration<String> headerNames = request.getHeaderNames();

        while (headerNames.hasMoreElements()) {
            String name = headerNames.nextElement();
            String value = request.getHeader(name);

            if (SENSITIVE_HEADERS.contains(name.toLowerCase())) {
                headers.put(name, maskSensitive(value));
            } else {
                headers.put(name, value);
            }
        }

        return headers;
    }

    /**
     * 脱敏敏感值
     */
    private String maskSensitive(String value) {
        if (value == null || value.length() <= 8) {
            return "***";
        }
        // 保留前4个和后4个字符
        return value.substring(0, 4) + "..." + value.substring(value.length() - 4);
    }

    /**
     * 响应包装器，用于捕获响应大小
     */
    private static class ContentCachingResponseWrapper extends jakarta.servlet.http.HttpServletResponseWrapper {

        private final java.io.ByteArrayOutputStream content = new java.io.ByteArrayOutputStream();
        private final jakarta.servlet.ServletOutputStream outputStream;
        private final jakarta.servlet.http.HttpServletResponse original;

        public ContentCachingResponseWrapper(jakarta.servlet.http.HttpServletResponse response) {
            super(response);
            this.original = response;
            try {
                this.outputStream = new ContentCachingServletOutputStream(content, response.getOutputStream());
            } catch (java.io.IOException e) {
                throw new RuntimeException("Failed to get output stream from response", e);
            }
        }

        @Override
        public jakarta.servlet.ServletOutputStream getOutputStream() throws IOException {
            return outputStream;
        }

        @Override
        public java.io.PrintWriter getWriter() throws IOException {
            return new java.io.PrintWriter(new java.io.OutputStreamWriter(content, getCharacterEncoding()), true);
        }

        public int getContentLength() {
            return content.size();
        }

        public void copyBodyToResponse() throws IOException {
            if (content.size() > 0) {
                original.getOutputStream().write(content.toByteArray());
                original.getOutputStream().flush();
            }
        }
    }

    /**
     * 用于捕获响应内容的 ServletOutputStream
     */
    private static class ContentCachingServletOutputStream extends jakarta.servlet.ServletOutputStream {

        private final java.io.ByteArrayOutputStream cache;
        private final jakarta.servlet.ServletOutputStream delegate;

        public ContentCachingServletOutputStream(java.io.ByteArrayOutputStream cache,
                                                  jakarta.servlet.ServletOutputStream delegate) {
            this.cache = cache;
            this.delegate = delegate;
        }

        @Override
        public void write(int b) throws IOException {
            cache.write(b);
        }

        @Override
        public void write(byte[] b, int off, int len) throws IOException {
            cache.write(b, off, len);
        }

        @Override
        public boolean isReady() {
            return delegate.isReady();
        }

        @Override
        public void setWriteListener(jakarta.servlet.WriteListener writeListener) {
            delegate.setWriteListener(writeListener);
        }
    }
}