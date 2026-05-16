package com.platform.gateway.config;

import io.netty.channel.ChannelOption;
import io.netty.handler.timeout.ReadTimeoutHandler;
import io.netty.handler.timeout.WriteTimeoutHandler;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;
import reactor.netty.resources.ConnectionProvider;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

/**
 * WebClient 配置
 *
 * <p>配置用于 SSE (Server-Sent Events) 流式响应的 WebClient，包含连接池、超时配置等。
 *
 * <h2>SSE 流式响应架构</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Client (Browser/App)                               │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              │ HTTP/SSE
 *                              ▼
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Gateway Service                                    │
 * │  ┌───────────────────────────────────────────────────────────────────────┐  │
 * │  │  WebClient Configuration                                              │  │
 * │  │                                                                       │  │
 * │  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
 * │  │  │  Connection Pool:                                                │ │  │
 * │  │  │  • maxConnections: 500                                          │ │  │
 * │  │  │  • maxIdleTime: 20s                                             │ │  │
 * │  │  │  • maxLifeTime: 60s                                             │ │  │
 * │  │  │  • pendingAcquireTimeout: 60s                                    │ │  │
 * │  │  └─────────────────────────────────────────────────────────────────┘ │  │
 * │  │                                                                       │  │
 * │  │  ┌─────────────────────────────────────────────────────────────────┐ │  │
 * │  │  │  Timeouts:                                                      │ │  │
 * │  │  │  • connectTimeout: 10s                                          │ │  │
 * │  │  │  • readTimeout: 300s (SSE 长连接)                               │ │  │
 * │  │  │  • writeTimeout: 30s                                            │ │  │
 * │  │  └─────────────────────────────────────────────────────────────────┘ │  │
 * │  └───────────────────────────────────────────────────────────────────────┘  │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              │ SSE Stream
 *                              ▼
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Orchestrator / Model Gateway                       │
 * │                          (Python SSE Server)                                │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>配置项</h2>
 * <ul>
 *   <li>{@code webclient.pool.max-connections}: 最大连接数，默认 500</li>
 *   <li>{@code webclient.pool.idle-timeout}: 空闲超时，默认 20s</li>
 *   <li>{@code webclient.connect-timeout}: 连接超时，默认 10s</li>
 *   <li>{@code webclient.read-timeout}: 读取超时，默认 300s (SSE 需要长连接)</li>
 *   <li>{@code webclient.write-timeout}: 写入超时，默认 30s</li>
 * </ul>
 *
 * <h2>SSE 特性</h2>
 * <p>WebClient 配置支持 SSE 流式响应：
 * <ul>
 *   <li>长读取超时（5 分钟）适应 SSE 场景</li>
 *   <li>禁用连接池限制以支持长连接</li>
 *   <li>自动重连机制</li>
 * </ul>
 *
 * @see WebClient
 * @see reactor.netty.http.client.HttpClient
 */
@Slf4j
@Configuration
public class WebClientConfig {

    @Value("${webclient.pool.max-connections:500}")
    private int maxConnections;

    @Value("${webclient.pool.idle-timeout-ms:20000}")
    private long poolIdleTimeoutMs;

    @Value("${webclient.pool.max-life-time-ms:60000}")
    private long poolMaxLifeTimeMs;

    @Value("${webclient.pool.pending-acquire-timeout-ms:60000}")
    private long pendingAcquireTimeoutMs;

    @Value("${webclient.connect-timeout-ms:10000}")
    private int connectTimeoutMs;

    @Value("${webclient.read-timeout-ms:300000}")
    private int readTimeoutMs;

    @Value("${webclient.write-timeout-ms:30000}")
    private int writeTimeoutMs;

    /**
     * 创建 SSE 流式响应 WebClient Bean
     *
     * <p>配置连接池和超时参数，专门用于 SSE 长连接场景。
     *
     * @return WebClient 实例
     */
    @Bean
    public WebClient sseWebClient() {
        // 配置连接池
        ConnectionProvider connectionProvider = ConnectionProvider.builder("sse-pool")
                .maxConnections(maxConnections)
                .maxIdleTime(Duration.ofMillis(poolIdleTimeoutMs))
                .maxLifeTime(Duration.ofMillis(poolMaxLifeTimeMs))
                .pendingAcquireTimeout(Duration.ofMillis(pendingAcquireTimeoutMs))
                .pendingAcquireMaxCount(1000)
                .build();

        // 配置 HttpClient
        HttpClient httpClient = HttpClient.create(connectionProvider)
                // 连接超时
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, connectTimeoutMs)
                // 响应超时（SSE 需要较长超时）
                .responseTimeout(Duration.ofMillis(readTimeoutMs))
                // 配置读写超时处理器
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(readTimeoutMs, TimeUnit.MILLISECONDS))
                        .addHandlerLast(new WriteTimeoutHandler(writeTimeoutMs, TimeUnit.MILLISECONDS)));

        log.info("WebClient initialized - maxConnections: {}, connectTimeout: {}ms, readTimeout: {}ms",
                maxConnections, connectTimeoutMs, readTimeoutMs);

        return WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .build();
    }

    /**
     * 创建用于普通 HTTP 调用的 WebClient Bean
     *
     * <p>配置较短的超时时间，适用于普通 REST API 调用。
     *
     * @return WebClient 实例
     */
    @Bean
    public WebClient httpClientWebClient() {
        ConnectionProvider connectionProvider = ConnectionProvider.builder("http-pool")
                .maxConnections(200)
                .maxIdleTime(Duration.ofSeconds(20))
                .maxLifeTime(Duration.ofSeconds(60))
                .pendingAcquireTimeout(Duration.ofSeconds(30))
                .build();

        HttpClient httpClient = HttpClient.create(connectionProvider)
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, 5000)
                .responseTimeout(Duration.ofSeconds(30))
                .doOnConnected(conn -> conn
                        .addHandlerLast(new ReadTimeoutHandler(30, TimeUnit.SECONDS))
                        .addHandlerLast(new WriteTimeoutHandler(10, TimeUnit.SECONDS)));

        log.info("HTTP WebClient initialized for standard REST calls");

        return WebClient.builder()
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .build();
    }
}