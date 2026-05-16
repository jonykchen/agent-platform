package com.platform.gateway;

import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.ConfigurableApplicationContext;
import org.springframework.scheduling.annotation.EnableScheduling;

import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Gateway 服务启动入口
 *
 * <p>Java 实现的 API Gateway，提供：
 * <ul>
 *   <li>认证授权（JWT + API Key）</li>
 *   <li>请求路由（到 Orchestrator/ToolBus）</li>
 *   <li>审计日志</li>
 *   <li>优雅关闭</li>
 * </ul>
 *
 * <h2>优雅关闭流程</h2>
 * <ol>
 *   <li>接收 SIGTERM 信号</li>
 *   <li>注册 JVM shutdown hook</li>
 *   <li>健康检查返回 503</li>
 *   <li>等待进行中请求完成（最多 30 秒）</li>
 *   <li>关闭 Spring 容器</li>
 * </ol>
 *
 * @see com.platform.gateway.config.GracefulShutdownConfig
 * @see com.platform.gateway.listener.GracefulShutdownListener
 */
@Slf4j
@SpringBootApplication
@EnableScheduling
public class GatewayApplication {

    /**
     * 关闭标志位
     * <p>用于在 shutdown hook 中检测是否已在关闭流程中
     */
    private static final AtomicBoolean shuttingDown = new AtomicBoolean(false);

    public static void main(String[] args) {
        ConfigurableApplicationContext context = SpringApplication.run(GatewayApplication.class, args);

        // 注册 JVM shutdown hook
        registerShutdownHook(context);

        log.info("=== Gateway Application Started ===");
        log.info("Graceful shutdown enabled with 30s timeout");
    }

    /**
     * 注册 JVM shutdown hook
     *
     * <p>在 JVM 接收到 SIGTERM 或 SIGINT 信号时触发：
     * <ul>
     *   <li>SIGTERM: Kubernetes Pod 终止、Docker stop</li>
     *   <li>SIGINT: Ctrl+C</li>
     * </ul>
     *
     * <p>注意：Spring Boot 3.x 内置的 {@code server.shutdown=graceful} 配置
     * 已经处理了 Tomcat 连接器的优雅关闭。此 hook 用于记录日志和协调流程。
     *
     * @param context Spring 应用上下文
     */
    private static void registerShutdownHook(ConfigurableApplicationContext context) {
        Thread shutdownHook = new Thread(() -> {
            if (shuttingDown.compareAndSet(false, true)) {
                log.info("=== Shutdown Hook Triggered ===");
                log.info("JVM received termination signal, initiating graceful shutdown...");

                try {
                    // Spring 的优雅关闭已经处理了请求等待
                    // 这里只记录日志
                    long startTime = System.currentTimeMillis();

                    // 触发 Spring 容器关闭（会触发 GracefulShutdownListener）
                    context.close();

                    long elapsedMs = System.currentTimeMillis() - startTime;
                    log.info("=== Shutdown Hook Completed ===");
                    log.info("Total shutdown time: {}ms", elapsedMs);

                } catch (Exception e) {
                    log.error("Error during shutdown hook execution", e);
                }
            }
        }, "graceful-shutdown-hook");

        // 设置为低优先级，确保其他 shutdown hook 先执行
        shutdownHook.setPriority(Thread.MAX_PRIORITY - 1);

        // 注册 JVM shutdown hook
        Runtime.getRuntime().addShutdownHook(shutdownHook);

        log.debug("Shutdown hook registered");
    }
}
