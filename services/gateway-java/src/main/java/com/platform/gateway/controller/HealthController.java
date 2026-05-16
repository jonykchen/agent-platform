package com.platform.gateway.controller;

import com.platform.gateway.config.GracefulShutdownConfig;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 健康检查控制器
 *
 * <p>提供服务健康状态和就绪状态检查端点：
 * <ul>
 *   <li>{@code /health} - 存活探针（Liveness Probe）</li>
 *   <li>{@code /ready} - 就绪探针（Readiness Probe）</li>
 * </ul>
 *
 * <h2>优雅关闭集成</h2>
 * <p>当服务进入优雅关闭流程时：
 * <ul>
 *   <li>{@code /health} 返回 503 状态码</li>
 *   <li>{@code /ready} 返回 503 状态码</li>
 * </ul>
 * <p>K8s 将从 Service 中移除该 Pod，不再转发新请求。
 *
 * @see GracefulShutdownConfig
 */
@RestController
@RequestMapping
@RequiredArgsConstructor
public class HealthController {

    private final GracefulShutdownConfig shutdownConfig;

    /**
     * 存活探针端点
     *
     * <p>K8s livenessProbe 使用此端点检测服务是否存活。
     * 返回 503 表示服务正在关闭，K8s 应停止转发请求。
     *
     * @return 健康状态响应
     */
    @GetMapping("/health")
    public ResponseEntity<Map<String, Object>> health() {
        if (shutdownConfig.isShuttingDown()) {
            return ResponseEntity
                    .status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(Map.of(
                            "status", "SHUTTING_DOWN",
                            "service", "gateway-java",
                            "message", "Service is shutting down",
                            "timestamp", System.currentTimeMillis()
                    ));
        }

        return ResponseEntity.ok(Map.of(
                "status", "UP",
                "service", "gateway-java",
                "timestamp", System.currentTimeMillis()
        ));
    }

    /**
     * 就绪探针端点
     *
     * <p>K8s readinessProbe 使用此端点检测服务是否准备好接收请求。
     * 返回 503 表示服务正在关闭，K8s 应将该 Pod 从 Service 中移除。
     *
     * @return 就绪状态响应
     */
    @GetMapping("/ready")
    public ResponseEntity<Map<String, Object>> ready() {
        if (shutdownConfig.isShuttingDown()) {
            return ResponseEntity
                    .status(HttpStatus.SERVICE_UNAVAILABLE)
                    .body(Map.of(
                            "status", "NOT_READY",
                            "service", "gateway-java",
                            "message", "Service is shutting down"
                    ));
        }

        return ResponseEntity.ok(Map.of(
                "status", "READY",
                "service", "gateway-java"
        ));
    }
}