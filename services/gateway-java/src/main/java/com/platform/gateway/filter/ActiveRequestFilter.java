package com.platform.gateway.filter;

import com.platform.gateway.config.GracefulShutdownConfig;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 活跃请求计数过滤器
 *
 * <p>追踪当前正在处理的请求数量，支持优雅关闭时等待所有请求完成。
 *
 * <h2>工作原理</h2>
 * <ol>
 *   <li>每个请求进入时，计数器 +1</li>
 *   <li>请求处理完成后，计数器 -1</li>
 *   <li>服务关闭时，通过 {@link #waitForCompletion(long)} 等待计数器归零</li>
 * </ol>
 *
 * <h2>线程安全</h2>
 * <p>使用 {@link AtomicInteger} 保证计数操作的原子性，支持高并发场景。
 *
 * <h2>配合组件</h2>
 * <ul>
 *   <li>{@link GracefulShutdownConfig} - 获取计数器实例</li>
 *   <li>{@link com.platform.gateway.listener.GracefulShutdownListener} - 关闭时等待请求完成</li>
 * </ul>
 *
 * @see GracefulShutdownConfig
 * @see com.platform.gateway.listener.GracefulShutdownListener
 */
@Slf4j
@Component
@Order(Ordered.HIGHEST_PRECEDENCE + 10)
public class ActiveRequestFilter extends OncePerRequestFilter {

    private final AtomicInteger activeRequestCount;

    /**
     * 构造函数
     *
     * @param gracefulShutdownConfig 优雅关闭配置，提供计数器实例
     */
    public ActiveRequestFilter(GracefulShutdownConfig gracefulShutdownConfig) {
        this.activeRequestCount = gracefulShutdownConfig.getActiveRequestCount();
    }

    /**
     * 请求处理过滤器
     * <p>在请求前后更新活跃请求计数
     *
     * @param request     HTTP 请求
     * @param response    HTTP 响应
     * @param filterChain 过滤器链
     */
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        int currentCount = activeRequestCount.incrementAndGet();
        String requestUri = request.getRequestURI();

        log.debug("Request started: {} (active: {})", requestUri, currentCount);

        try {
            filterChain.doFilter(request, response);
        } finally {
            currentCount = activeRequestCount.decrementAndGet();
            log.debug("Request completed: {} (active: {})", requestUri, currentCount);
        }
    }

    /**
     * 获取当前活跃请求数量
     *
     * @return 当前正在处理的请求数量
     */
    public int getActiveRequestCount() {
        return activeRequestCount.get();
    }

    /**
     * 等待所有活跃请求完成
     *
     * <p>阻塞当前线程，直到所有请求处理完成或超时。
     * 使用轮询方式检查计数器，每 100ms 检查一次。
     *
     * <h2>使用场景</h2>
     * <pre>{@code
     * // 在关闭监听器中等待请求完成
     * boolean completed = filter.waitForCompletion(30_000);
     * if (!completed) {
     *     log.warn("Some requests did not complete in time");
     * }
     * }</pre>
     *
     * @param timeoutMs 超时时间（毫秒）
     * @return true 表示所有请求已完成；false 表示超时或被中断
     */
    public boolean waitForCompletion(long timeoutMs) {
        if (activeRequestCount.get() == 0) {
            log.info("No active requests, proceeding with shutdown");
            return true;
        }

        log.info("Waiting for {} active requests to complete (timeout: {}ms)",
                activeRequestCount.get(), timeoutMs);

        long startTime = System.currentTimeMillis();
        long remainingTime = timeoutMs;
        long pollInterval = 100; // 轮询间隔（毫秒）

        while (activeRequestCount.get() > 0 && remainingTime > 0) {
            try {
                TimeUnit.MILLISECONDS.sleep(Math.min(pollInterval, remainingTime));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                log.warn("Interrupted while waiting for active requests");
                return false;
            }

            remainingTime = timeoutMs - (System.currentTimeMillis() - startTime);

            // 每秒输出一次等待日志
            if ((System.currentTimeMillis() - startTime) % 1000 < pollInterval) {
                log.debug("Still waiting for {} active requests (remaining: {}ms)",
                        activeRequestCount.get(), remainingTime);
            }
        }

        boolean completed = activeRequestCount.get() == 0;

        if (completed) {
            log.info("All active requests completed in {}ms",
                    System.currentTimeMillis() - startTime);
        } else {
            log.warn("Timeout waiting for active requests, {} requests still pending",
                    activeRequestCount.get());
        }

        return completed;
    }

    /**
     * 判断是否应该跳过此过滤器
     * <p>健康检查端点跳过计数，避免影响关闭流程中的健康检查
     *
     * @param request HTTP 请求
     * @return true 表示跳过此过滤器
     */
    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // 健康检查和就绪探针端点不计数
        String path = request.getRequestURI();
        return path.equals("/health") || path.equals("/ready") ||
               path.startsWith("/actuator/");
    }
}