package com.platform.gateway.middleware;

import com.platform.gateway.config.RateLimitConfig;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.TenantContextService;
import io.github.bucket4j.Bucket;
import io.github.bucket4j.ConsumptionProbe;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

/**
 * 速率限制过滤器
 *
 * <p>基于 Bucket4j 实现请求速率限制，支持用户级和租户级限流。
 *
 * <h2>限流架构</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          请求入口                                           │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              ▼
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │  RateLimitingFilter                                                         │
 * │  ┌───────────────────────────────────────────────────────────────────────┐ │
 * │  │  1. 提取 user_id 和 tenant_id                                          │ │
 * │  │  2. 检查用户级 Bucket                                                   │ │
 * │  │  3. 检查租户级 Bucket                                                   │ │
 * │  │  4. 通过：继续处理请求                                                   │ │
 * │  │  5. 拒绝：返回 HTTP 429                                                 │ │
 * │  └───────────────────────────────────────────────────────────────────────┘ │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>响应头</h2>
 * <ul>
 *   <li>X-RateLimit-Limit: 限制值</li>
 *   <li>X-RateLimit-Remaining: 剩余配额</li>
 *   <li>X-RateLimit-Reset: 重置时间（秒）</li>
 * </ul>
 *
 * <h2>Filter 顺序</h2>
 * <pre>
 * Request → RequestIdFilter(1) → TenantContextFilter(2) → LoggingFilter(3) → TimingFilter(4) → RateLimitingFilter(5) → AuthFilter → Controller
 * </pre>
 *
 * @see com.platform.gateway.config.RateLimitConfig
 * @see io.github.bucket4j.Bucket
 */
@Slf4j
@Component
@Order(5)
@RequiredArgsConstructor
public class RateLimitingFilter implements Filter {

    private static final String RATE_LIMIT_HEADER = "X-RateLimit-Limit";
    private static final String RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Remaining";
    private static final String RATE_LIMIT_RESET_HEADER = "X-RateLimit-Reset";
    private static final String RETRY_AFTER_HEADER = "Retry-After";

    private final com.platform.gateway.config.BucketManager bucketManager;
    private final RateLimitConfig rateLimitConfig;
    private final TenantContextService tenantContextService;

    @Value("${rate-limit.enabled:true}")
    private boolean rateLimitEnabled;

    @Value("${rate-limit.user.rpm:60}")
    private int userRpm;

    @Value("${rate-limit.tenant.tpm:100000}")
    private int tenantTpm;

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        // 限流开关检查
        if (!rateLimitEnabled) {
            chain.doFilter(request, response);
            return;
        }

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        // 跳过健康检查等路径
        String path = httpRequest.getRequestURI();
        if (shouldSkipRateLimit(path)) {
            chain.doFilter(request, response);
            return;
        }

        // 获取用户 ID 和租户 ID
        String userId = tenantContextService.getCurrentUserId();
        String tenantId = tenantContextService.getCurrentTenantId();

        if (userId == null || userId.equals("anonymous")) {
            // 未认证用户，使用 IP 作为限流键
            userId = "ip:" + getClientIp(httpRequest);
        }

        if (tenantId == null) {
            tenantId = "default";
        }

        // 检查用户级限流
        Bucket userBucket = bucketManager.getUserBucket(userId, rateLimitConfig.userBucketConfiguration());
        ConsumptionProbe userProbe = userBucket.tryConsumeAndReturnRemaining(1);

        if (!userProbe.isConsumed()) {
            log.warn("User rate limit exceeded: userId={}, tenantId={}", userId, tenantId);
            handleRateLimitExceeded(httpResponse, userProbe, userRpm);
            return;
        }

        // 检查租户级限流（仅对认证用户）
        if (!tenantId.equals("default")) {
            Bucket tenantBucket = bucketManager.getTenantBucket(tenantId, rateLimitConfig.tenantBucketConfiguration());
            // 租户级使用估算的 token 消耗（实际应在响应后更新）
            ConsumptionProbe tenantProbe = tenantBucket.tryConsumeAndReturnRemaining(100); // 预估 100 tokens

            if (!tenantProbe.isConsumed()) {
                log.warn("Tenant rate limit exceeded: tenantId={}", tenantId);
                handleRateLimitExceeded(httpResponse, tenantProbe, tenantTpm);
                return;
            }
        }

        // 设置响应头
        setRateLimitHeaders(httpResponse, userProbe, userRpm);

        try {
            chain.doFilter(request, response);
        } finally {
            // 如果需要，可以根据实际 token 使用量更新租户 Bucket
            // 这里暂时使用预估方式
        }
    }

    /**
     * 判断是否跳过限流
     */
    private boolean shouldSkipRateLimit(String path) {
        return path.startsWith("/health") ||
               path.startsWith("/ready") ||
               path.startsWith("/actuator") ||
               path.startsWith("/favicon") ||
               path.startsWith("/static/") ||
               path.startsWith("/error");
    }

    /**
     * 获取客户端 IP
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
     * 处理限流超限
     */
    private void handleRateLimitExceeded(HttpServletResponse response,
                                         ConsumptionProbe probe,
                                         int limit) throws IOException {
        response.setStatus(429); // HTTP 429 Too Many Requests
        response.setHeader(RATE_LIMIT_HEADER, String.valueOf(limit));
        response.setHeader(RATE_LIMIT_REMAINING_HEADER, "0");

        long waitForRefill = probe.getNanosToWaitForRefill();
        long resetSeconds = TimeUnit.NANOSECONDS.toSeconds(waitForRefill);
        response.setHeader(RATE_LIMIT_RESET_HEADER, String.valueOf(resetSeconds));
        response.setHeader(RETRY_AFTER_HEADER, String.valueOf(Math.max(1, resetSeconds)));

        response.setContentType("application/json");
        response.setCharacterEncoding("UTF-8");

        String errorResponse = String.format(
                "{\"error\":\"ERR_RATE_LIMITED\",\"message\":\"Rate limit exceeded. Please retry after %d seconds.\",\"user_message\":\"请求过于频繁，请稍后重试\",\"retry_after\":%d}",
                Math.max(1, resetSeconds),
                Math.max(1, resetSeconds)
        );

        response.getWriter().write(errorResponse);
    }

    /**
     * 设置限流响应头
     */
    private void setRateLimitHeaders(HttpServletResponse response, ConsumptionProbe probe, int limit) {
        response.setHeader(RATE_LIMIT_HEADER, String.valueOf(limit));
        response.setHeader(RATE_LIMIT_REMAINING_HEADER, String.valueOf(probe.getRemainingTokens()));

        if (probe.getNanosToWaitForRefill() > 0) {
            long resetSeconds = TimeUnit.NANOSECONDS.toSeconds(probe.getNanosToWaitForRefill());
            response.setHeader(RATE_LIMIT_RESET_HEADER, String.valueOf(resetSeconds));
        }
    }
}