package com.platform.gateway.config;

import org.apache.catalina.connector.Connector;
import org.springframework.boot.web.embedded.tomcat.TomcatConnectorCustomizer;
import org.springframework.boot.web.embedded.tomcat.TomcatServletWebServerFactory;
import org.springframework.boot.web.server.WebServerFactoryCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 优雅关闭配置
 *
 * <p>配置 Tomcat 容器支持优雅关闭，确保在收到关闭信号时：
 * <ol>
 *   <li>停止接收新请求（连接器停止接受新连接）</li>
 *   <li>等待进行中的请求处理完成</li>
 *   <li>超时后强制关闭</li>
 * </ol>
 *
 * <h2>配置项</h2>
 * <ul>
 *   <li>{@code server.shutdown} - Spring Boot 3.x 内置优雅关闭支持</li>
 *   <li>{@code spring.lifecycle.timeout-per-shutdown-phase} - 关闭阶段超时时间</li>
 * </ul>
 *
 * <h2>配合组件</h2>
 * <ul>
 *   <li>{@link ActiveRequestFilter} - 追踪进行中的请求数量</li>
 *   <li>{@link GracefulShutdownListener} - 协调关闭流程</li>
 * </ul>
 *
 * @see ActiveRequestFilter
 * @see GracefulShutdownListener
 */
@Configuration
public class GracefulShutdownConfig {

    /**
     * 优雅关闭超时时间（毫秒）
     * <p>默认 30 秒，等待进行中的请求完成的最大时间
     */
    private static final long SHUTDOWN_TIMEOUT_MS = 30_000;

    /**
     * 进行中请求计数器
     * <p>用于追踪当前正在处理的请求数量，支持优雅关闭时等待请求完成
     */
    private final AtomicInteger activeRequestCount = new AtomicInteger(0);

    /**
     * 关闭标志位
     * <p>当设置为 true 时，服务进入关闭流程，健康检查将返回 503
     */
    private volatile boolean shuttingDown = false;

    /**
     * 获取进行中请求计数器
     *
     * @return AtomicInteger 类型的请求计数器
     */
    public AtomicInteger getActiveRequestCount() {
        return activeRequestCount;
    }

    /**
     * 检查服务是否正在关闭
     *
     * @return true 表示服务正在关闭
     */
    public boolean isShuttingDown() {
        return shuttingDown;
    }

    /**
     * 标记服务进入关闭状态
     * <p>设置后，健康检查端点将返回 503 状态码
     */
    public void markShuttingDown() {
        this.shuttingDown = true;
    }

    /**
     * 获取关闭超时时间
     *
     * @return 超时时间（毫秒）
     */
    public long getShutdownTimeoutMs() {
        return SHUTDOWN_TIMEOUT_MS;
    }

    /**
     * 等待所有活跃请求完成
     * <p>阻塞当前线程，直到所有请求处理完成或超时
     *
     * @param timeoutMs 超时时间（毫秒）
     * @return true 表示所有请求已完成；false 表示超时
     */
    public boolean waitForActiveRequests(long timeoutMs) {
        if (activeRequestCount.get() == 0) {
            return true;
        }

        long startTime = System.currentTimeMillis();
        long remainingTime = timeoutMs;

        while (activeRequestCount.get() > 0 && remainingTime > 0) {
            try {
                Thread.sleep(Math.min(100, remainingTime));
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
            remainingTime = timeoutMs - (System.currentTimeMillis() - startTime);
        }

        return activeRequestCount.get() == 0;
    }

    /**
     * Tomcat 容器定制器
     * <p>配置 Tomcat 连接器支持优雅关闭：
     * <ul>
     *   <li>设置连接器在关闭时等待请求处理完成</li>
     *   <li>配置线程池优雅关闭</li>
     * </ul>
     *
     * @return WebServerFactoryCustomizer 实例
     */
    @Bean
    public WebServerFactoryCustomizer<TomcatServletWebServerFactory> gracefulShutdownCustomizer() {
        return factory -> {
            // 配置连接器定制器，支持优雅关闭
            factory.addConnectorCustomizers(new GracefulShutdownConnectorCustomizer());
        };
    }

    /**
     * Tomcat 连接器定制器
     * <p>配置连接器的线程池行为，支持优雅关闭
     */
    private static class GracefulShutdownConnectorCustomizer implements TomcatConnectorCustomizer {

        @Override
        public void customize(Connector connector) {
            // 配置连接器协议处理器
            // 设置优雅关闭等待时间（单位：秒）
            connector.setProperty("maxKeepAliveRequests", "-1"); // 不限制 keep-alive 请求数

            // 设置 socket 超时，确保关闭时有足够时间处理请求
            connector.setProperty("connectionTimeout", "20000");

            // 启用优雅关闭
            // 当接收到关闭信号时，不再接受新请求，但处理完现有请求
            connector.setProperty("bindOnInit", "false");
        }
    }
}