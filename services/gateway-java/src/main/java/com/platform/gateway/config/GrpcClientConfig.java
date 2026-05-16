package com.platform.gateway.config;

import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.netty.shaded.io.grpc.netty.NettyChannelBuilder;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import jakarta.annotation.PreDestroy;
import java.util.concurrent.TimeUnit;

/**
 * gRPC 客户端配置
 *
 * <p>配置到 Orchestrator 服务的 gRPC 客户端连接，包含连接池、Keep-alive、超时等参数。
 *
 * <h2>连接架构</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Gateway Service                                    │
 * │  ┌───────────────────────────────────────────────────────────────────────┐  │
 * │  │  gRPC Client Configuration                                            │  │
 * │  │                                                                       │  │
 * │  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
 * │  │  │  ManagedChannel (单例)                                           │ │  │
 * │  │  │  ┌─────────────────────────────────────────────────────────────┐ │ │  │
 * │  │  │  │  连接池配置:                                                 │ │ │  │
 * │  │  │  │  • maxInboundMessageSize: 16MB                              │ │ │  │
 * │  │  │  │  • keepAliveTime: 30s                                       │ │ │  │
 * │  │  │  │  • keepAliveTimeout: 10s                                     │ │ │  │
 * │  │  │  │  • keepAliveWithoutCalls: true                              │ │ │  │
 * │  │  │  │  • idleTimeout: 5m                                          │ │ │  │
 * │  │  │  └─────────────────────────────────────────────────────────────┘ │ │  │
 * │  │  └─────────────────────────────────────────────────────────────────┘ │  │
 * │  └───────────────────────────────────────────────────────────────────────┘  │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              │ gRPC
 *                              ▼
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Orchestrator Service                               │
 * │                          (Python gRPC Server)                              │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>配置项</h2>
 * <ul>
 *   <li>{@code orchestrator.grpc.host}: Orchestrator 服务地址，默认 localhost</li>
 *   <li>{@code orchestrator.grpc.port}: Orchestrator 服务端口，默认 50051</li>
 *   <li>{@code orchestrator.grpc.timeout-ms}: 默认调用超时，默认 30000ms</li>
 *   <li>{@code orchestrator.grpc.keepalive-time-ms}: Keep-alive 间隔，默认 30000ms</li>
 *   <li>{@code orchestrator.grpc.keepalive-timeout-ms}: Keep-alive 超时，默认 10000ms</li>
 *   <li>{@code orchestrator.grpc.max-inbound-message-size}: 最大消息大小，默认 16MB</li>
 * </ul>
 *
 * <h2>Keep-alive 机制</h2>
 * <p>启用 Keep-alive 可以：
 * <ul>
 *   <li>保持连接活跃，避免防火墙超时断开</li>
 *   <li>快速检测连接故障</li>
 *   <li>减少连接重建开销</li>
 * </ul>
 *
 * @see ManagedChannel
 * @see io.grpc.ManagedChannelBuilder
 */
@Slf4j
@Configuration
public class GrpcClientConfig {

    @Value("${orchestrator.grpc.host:localhost}")
    private String orchestratorHost;

    @Value("${orchestrator.grpc.port:50051}")
    private int orchestratorPort;

    @Value("${orchestrator.grpc.timeout-ms:30000}")
    private int defaultTimeoutMs;

    @Value("${orchestrator.grpc.keepalive-time-ms:30000}")
    private int keepaliveTimeMs;

    @Value("${orchestrator.grpc.keepalive-timeout-ms:10000}")
    private int keepaliveTimeoutMs;

    @Value("${orchestrator.grpc.max-inbound-message-size:16777216}")
    private int maxInboundMessageSize;

    @Value("${orchestrator.grpc.idle-timeout-ms:300000}")
    private int idleTimeoutMs;

    @Value("${orchestrator.grpc.enable-retry:true}")
    private boolean enableRetry;

    @Value("${orchestrator.grpc.max-retry-attempts:3}")
    private int maxRetryAttempts;

    private ManagedChannel managedChannel;

    /**
     * 创建 gRPC ManagedChannel Bean
     *
     * <p>配置连接池参数和 Keep-alive 机制，确保长期稳定的 gRPC 连接。
     *
     * @return ManagedChannel 单例
     */
    @Bean
    public ManagedChannel orchestratorChannel() {
        log.info("Initializing gRPC channel to {}:{}", orchestratorHost, orchestratorPort);

        ManagedChannelBuilder<?> channelBuilder = ManagedChannelBuilder
                .forAddress(orchestratorHost, orchestratorPort)
                .usePlaintext()
                // 消息大小配置
                .maxInboundMessageSize(maxInboundMessageSize)
                // Keep-alive 配置
                .keepAliveTime(keepaliveTimeMs, TimeUnit.MILLISECONDS)
                .keepAliveTimeout(keepaliveTimeoutMs, TimeUnit.MILLISECONDS)
                .keepAliveWithoutCalls(true)
                // 空闲超时
                .idleTimeout(idleTimeoutMs, TimeUnit.MILLISECONDS);

        // 重试配置
        if (enableRetry) {
            channelBuilder
                    .enableRetry()
                    .maxRetryAttempts(maxRetryAttempts);
        }

        managedChannel = channelBuilder.build();

        log.info("gRPC channel initialized successfully - host: {}, port: {}, keepAlive: {}ms, timeout: {}ms",
                orchestratorHost, orchestratorPort, keepaliveTimeMs, defaultTimeoutMs);

        return managedChannel;
    }

    /**
     * 获取默认超时时间
     *
     * @return 默认超时时间（毫秒）
     */
    public int getDefaultTimeoutMs() {
        return defaultTimeoutMs;
    }

    /**
     * 应用关闭时优雅关闭 gRPC Channel
     *
     * <p>等待最多 5 秒完成正在处理的请求，然后强制关闭。
     */
    @PreDestroy
    public void shutdown() {
        if (managedChannel != null && !managedChannel.isShutdown()) {
            log.info("Shutting down gRPC channel...");
            try {
                managedChannel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
                log.info("gRPC channel shutdown completed gracefully");
            } catch (InterruptedException e) {
                log.warn("gRPC channel shutdown interrupted, forcing immediate shutdown");
                managedChannel.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }
    }
}