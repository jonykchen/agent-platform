package com.platform.gateway.config;

import io.opentelemetry.api.OpenTelemetry;
import io.opentelemetry.api.common.AttributeKey;
import io.opentelemetry.api.common.Attributes;
import io.opentelemetry.api.trace.Tracer;
import io.opentelemetry.context.propagation.TextMapPropagator;
import io.opentelemetry.exporter.otlp.trace.OtlpGrpcSpanExporter;
import io.opentelemetry.sdk.OpenTelemetrySdk;
import io.opentelemetry.sdk.resources.Resource;
import io.opentelemetry.sdk.trace.SdkTracerProvider;
import io.opentelemetry.sdk.trace.export.BatchSpanProcessor;
import io.opentelemetry.sdk.trace.samplers.Sampler;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenTelemetry 配置
 *
 * <p>配置分布式追踪和指标收集，支持 OTLP 协议导出到 Jaeger/Zipkin 等。
 *
 * <h2>追踪架构</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          Gateway Service                                    │
 * │                                                                             │
 * │  ┌─────────────────────────────────────────────────────────────────────┐   │
 * │  │  OTel SDK Configuration                                             │   │
 * │  │                                                                     │   │
 * │  │  ┌───────────────────────────────────────────────────────────────┐  │   │
 * │  │  │  TracerProvider                                               │  │   │
 * │  │  │  ┌─────────────────────────────────────────────────────────┐  │  │   │
 * │  │  │  │  Span Processors:                                       │  │  │   │
 * │  │  │  │  • BatchSpanProcessor (批量导出，性能优化)               │  │  │   │
 * │  │  │  │  • Sampler: ParentBased (基于父 Span 决策)               │  │  │   │
 * │  │  │  └─────────────────────────────────────────────────────────┘  │  │   │
 * │  │  └───────────────────────────────────────────────────────────────┘  │   │
 * │  │                                                                     │   │
 * │  │  ┌───────────────────────────────────────────────────────────────┐  │   │
 * │  │  │  Resource                                                     │  │   │
 * │  │  │  • service.name: gateway-java                                 │  │   │
 * │  │  │  • service.version: 1.0.0                                    │  │   │
 * │  │  │  • deployment.environment: prod/local                        │  │   │
 * │  │  └───────────────────────────────────────────────────────────────┘  │   │
 * │  └─────────────────────────────────────────────────────────────────────┘   │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *                              │
 *                              │ OTLP (gRPC)
 *                              ▼
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          OTLP Collector                                     │
 * │                          (Jaeger / Zipkin / Tempo)                         │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>配置项</h2>
 * <ul>
 *   <li>{@code otel.exporter.otlp.endpoint}: OTLP Collector 地址，默认 localhost:4317</li>
 *   <li>{@code otel.service.name}: 服务名称，默认 gateway-java</li>
 *   <li>{@code otel.traces.sampler}: 采样策略，默认 parentbased_traceidratio</li>
 *   <li>{@code otel.traces.sampler.arg}: 采样率，默认 1.0 (100%)</li>
 * </ul>
 *
 * <h2>自动 Instrumentation</h2>
 * <p>以下组件自动生成 Span：
 * <ul>
 *   <li>Spring MVC Controllers</li>
 *   <li>Spring Security Filters</li>
 *   <li>HTTP Client 调用</li>
 *   <li>gRPC Client/Server</li>
 *   <li>JDBC 操作</li>
 * </ul>
 *
 * <h2>Trace Context 传播</h2>
 * <p>支持以下传播格式：
 * <ul>
 *   <li>W3C Trace Context (标准)</li>
 *   <li>W3C Baggage</li>
 *   <li>B3 (Zipkin 兼容)</li>
 *   <li>Jaeger (Uber)</li>
 * </ul>
 *
 * @see OpenTelemetry
 * @see io.opentelemetry.sdk.trace.SdkTracerProvider
 */
@Slf4j
@Configuration
public class OpenTelemetryConfig {

    @Value("${otel.exporter.otlp.endpoint:http://localhost:4317}")
    private String otlpEndpoint;

    @Value("${otel.service.name:gateway-java}")
    private String serviceName;

    @Value("${otel.service.version:1.0.0}")
    private String serviceVersion;

    @Value("${otel.traces.sampler.arg:1.0}")
    private double samplerRatio;

    @Value("${otel.exporter.batch.schedule.delay.ms:5000}")
    private long batchScheduleDelayMs;

    @Value("${otel.exporter.batch.max.queue.size:2048}")
    private int maxQueueSize;

    @Value("${otel.exporter.batch.max.export.batch.size:512}")
    private int maxExportBatchSize;

    @Value("${otel.exporter.batch.export.timeout.ms:30000}")
    private long exportTimeoutMs;

    /**
     * 创建 OTLP Span Exporter Bean
     *
     * <p>使用 gRPC 协议导出 Span 到 OTLP Collector。
     *
     * @return OtlpGrpcSpanExporter 实例
     */
    @Bean
    public OtlpGrpcSpanExporter otlpGrpcSpanExporter() {
        log.info("Initializing OTLP Span Exporter - endpoint: {}, service: {}",
                otlpEndpoint, serviceName);

        return OtlpGrpcSpanExporter.builder()
                .setEndpoint(otlpEndpoint)
                .setTimeout(exportTimeoutMs, java.util.concurrent.TimeUnit.MILLISECONDS)
                .build();
    }

    /**
     * 创建资源定义 Bean
     *
     * <p>定义服务的资源属性，用于标识 Span 来源。
     *
     * @return Resource 实例
     */
    @Bean
    public Resource otelResource() {
        return Resource.getDefault()
                .merge(Resource.create(Attributes.of(
                        AttributeKey.stringKey("service.name"), serviceName,
                        AttributeKey.stringKey("service.version"), serviceVersion,
                        AttributeKey.stringKey("deployment.environment"),
                        System.getProperty("spring.profiles.active", "unknown"))));
    }

    /**
     * 创建 TracerProvider Bean
     *
     * <p>配置追踪提供者，包含采样策略和批量导出处理器。
     *
     * @param spanExporter OTLP Span Exporter
     * @param resource 资源定义
     * @return SdkTracerProvider 实例
     */
    @Bean
    public SdkTracerProvider sdkTracerProvider(
            OtlpGrpcSpanExporter spanExporter,
            Resource resource) {

        // 批量导出处理器（性能优化）
        BatchSpanProcessor batchSpanProcessor = BatchSpanProcessor.builder(spanExporter)
                .setScheduleDelay(java.time.Duration.ofMillis(batchScheduleDelayMs))
                .setMaxQueueSize(maxQueueSize)
                .setMaxExportBatchSize(maxExportBatchSize)
                .setExporterTimeout(java.time.Duration.ofMillis(exportTimeoutMs))
                .build();

        // 采样策略：ParentBased + TraceIdRatio
        // ParentBased: 遵循父 Span 的采样决策
        // TraceIdRatio: 按 TraceID 比例采样
        Sampler sampler = Sampler.parentBased(Sampler.traceIdRatioBased(samplerRatio));

        log.info("TracerProvider initialized - sampler ratio: {}, batch size: {}",
                samplerRatio, maxExportBatchSize);

        return SdkTracerProvider.builder()
                .setResource(resource)
                .addSpanProcessor(batchSpanProcessor)
                .setSampler(sampler)
                .build();
    }

    /**
     * 创建 OpenTelemetry SDK Bean
     *
     * <p>整合 TracerProvider 和 Propagator，提供完整的 OpenTelemetry 功能。
     *
     * @param tracerProvider TracerProvider
     * @return OpenTelemetrySdk 实例
     */
    @Bean
    public OpenTelemetrySdk openTelemetrySdk(SdkTracerProvider tracerProvider) {
        // 支持 W3C Trace Context 和 Baggage
        TextMapPropagator propagator = TextMapPropagator.composite(
                io.opentelemetry.context.propagation.TextMapPropagator.composite(
                        io.opentelemetry.api.trace.propagation.W3CTraceContextPropagator.getInstance(),
                        io.opentelemetry.api.baggage.propagation.W3CBaggagePropagator.getInstance()
                )
        );

        log.info("OpenTelemetry SDK initialized successfully");

        return OpenTelemetrySdk.builder()
                .setTracerProvider(tracerProvider)
                .setPropagators(io.opentelemetry.context.propagation.ContextPropagators.create(propagator))
                .build();
    }

    /**
     * 创建 Tracer Bean
     *
     * <p>用于手动创建 Span。
     *
     * @param openTelemetry OpenTelemetry SDK
     * @return Tracer 实例
     */
    @Bean
    public Tracer tracer(OpenTelemetry openTelemetry) {
        return openTelemetry.getTracer(serviceName, serviceVersion);
    }
}