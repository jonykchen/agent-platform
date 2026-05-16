package com.platform.gateway.listener;

import com.platform.gateway.config.GracefulShutdownConfig;
import com.platform.gateway.filter.ActiveRequestFilter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationListener;
import org.springframework.context.event.ContextClosedEvent;
import org.springframework.stereotype.Component;

/**
 * 优雅关闭监听器
 *
 * <p>监听 Spring 容器关闭事件，协调优雅关闭流程：
 * <ol>
 *   <li>标记服务为关闭中状态（健康检查返回 503）</li>
 *   <li>等待进行中的请求处理完成</li>
 *   <li>超时后继续关闭流程</li>
 * </ol>
 *
 * <h2>关闭时序</h2>
 * <pre>
 * SIGTERM 接收
 *     ↓
 * ContextClosedEvent 触发
 *     ↓
 * 1. 标记 shuttingDown = true
 * 2. 健康检查返回 503（K8s 从 Service 移除）
 * 3. 等待活跃请求完成（最多 30 秒）
 *     ↓
 * 容器关闭（连接器停止、线程池销毁）
 *     ↓
 * JVM 退出
 * </pre>
 *
 * <h2>K8s 集成</h2>
 * <ul>
 *   <li>配置 preStop 钩子：发送 SIGTERM 前，先从 Service 移除</li>
 *   <li>配置 terminationGracePeriodSeconds：至少 60 秒</li>
 *   <li>配置 readinessProbe：指向 /ready 端点</li>
 * </ul>
 *
 * <h2>配置示例</h2>
 * <pre>{@code
 * # application.yml
 * server:
 *   shutdown: graceful
 * spring:
 *   lifecycle:
 *     timeout-per-shutdown-phase: 30s
 * }</pre>
 *
 * <h2>K8s Deployment 示例</h2>
 * <pre>{@code
 * spec:
 *   containers:
 *   - name: gateway
 *     lifecycle:
 *       preStop:
 *         exec:
 *           command: ["/bin/sh", "-c", "sleep 5"]
 *     readinessProbe:
 *       httpGet:
 *         path: /ready
 *         port: 8080
 *   terminationGracePeriodSeconds: 60
 * }</pre>
 *
 * @see GracefulShutdownConfig
 * @see ActiveRequestFilter
 */
@Slf4j
@Component
public class GracefulShutdownListener implements ApplicationListener<ContextClosedEvent> {

    private final GracefulShutdownConfig shutdownConfig;
    private final ActiveRequestFilter activeRequestFilter;

    /**
     * 构造函数
     *
     * @param shutdownConfig      优雅关闭配置
     * @param activeRequestFilter 活跃请求过滤器
     */
    public GracefulShutdownListener(GracefulShutdownConfig shutdownConfig,
                                    ActiveRequestFilter activeRequestFilter) {
        this.shutdownConfig = shutdownConfig;
        this.activeRequestFilter = activeRequestFilter;
    }

    /**
     * 处理容器关闭事件
     *
     * <p>执行优雅关闭流程：
     * <ol>
     *   <li>标记服务为关闭中状态</li>
     *   <li>等待活跃请求完成</li>
     *   <li>记录关闭日志</li>
     * </ol>
     *
     * @param event 上下文关闭事件
     */
    @Override
    public void onApplicationEvent(ContextClosedEvent event) {
        log.info("=== Graceful Shutdown Initiated ===");
        log.info("Active requests: {}", activeRequestFilter.getActiveRequestCount());

        long startTime = System.currentTimeMillis();

        // 步骤 1: 标记服务为关闭中状态
        // 健康检查端点将返回 503，K8s readinessProbe 将 Pod 标记为不健康
        shutdownConfig.markShuttingDown();
        log.info("Service marked as shutting down, health check will return 503");

        // 步骤 2: 等待活跃请求完成
        long timeoutMs = shutdownConfig.getShutdownTimeoutMs();
        boolean allCompleted = activeRequestFilter.waitForCompletion(timeoutMs);

        long elapsedMs = System.currentTimeMillis() - startTime;

        if (allCompleted) {
            log.info("=== Graceful Shutdown Completed ===");
            log.info("All requests processed, shutdown time: {}ms", elapsedMs);
        } else {
            log.warn("=== Graceful Shutdown Timeout ===");
            log.warn("Some requests did not complete, shutdown time: {}ms, remaining: {}",
                    elapsedMs, activeRequestFilter.getActiveRequestCount());
        }
    }
}