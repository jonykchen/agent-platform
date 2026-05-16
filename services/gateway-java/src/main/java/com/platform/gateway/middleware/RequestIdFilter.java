package com.platform.gateway.middleware;

import com.platform.gateway.util.RequestIdGenerator;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;

/**
 * Request ID 过滤器 - 全链路追踪入口点
 *
 * <h2>核心概念</h2>
 * <p>
 * Request ID 是分布式系统中用于全链路追踪的唯一标识符。本过滤器作为 Gateway 层的入口，
 * 负责生成或传递 request_id，并通过 SLF4J MDC (Mapped Diagnostic Context) 机制
 * 使其在整个请求生命周期内可被日志框架自动获取。
 * </p>
 *
 * <h2>Request ID 生成策略</h2>
 * <table border="1">
 *   <tr><th>策略</th><th>格式示例</th><th>优点</th><th>缺点</th><th>适用场景</th></tr>
 *   <tr>
 *     <td><b>UUID v7</b></td>
 *     <td>018f3b2a-1c4d-7d8e-9f0a-1b2c3d4e5f6g</td>
 *     <td>时间有序、数据库友好、碰撞概率极低</td>
 *     <td>需实现算法、长度较长</td>
 *     <td><b>本项目采用</b>、分布式追踪</td>
 *   </tr>
 *   <tr>
 *     <td>UUID v4</td>
 *     <td>a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d</td>
 *     <td>碰撞概率低、广泛支持</td>
 *     <td>无序、数据库索引效率低</td>
 *     <td>通用场景</td>
 *   </tr>
 *   <tr>
 *     <td>NanoID</td>
 *     <td>V1StGXR8_Z5jdHi6B-myT</td>
 *     <td>短小、URL 安全、可配置长度</td>
 *     <td>无序、需引入依赖</td>
 *     <td>短链接、前端场景</td>
 *   </tr>
 *   <tr>
 *     <td>时间戳+随机数</td>
 *     <td>20240605123456abc123</td>
 *     <td>可读性好、时间有序</td>
 *     <td>碰撞风险、长度不固定</td>
 *     <td>简单应用、调试场景</td>
 *   </tr>
 * </table>
 *
 * <h2>技术选型：UUID v7</h2>
 * <p>
 * 本项目采用 UUID v7 作为 Request ID 生成策略，核心优势：
 * </p>
 * <ul>
 *   <li><b>时间有序</b>：前 48 位为毫秒级时间戳，支持按时间范围高效查询</li>
 *   <li><b>数据库友好</b>：有序插入减少 B+ 树页分裂，提升写入性能</li>
 *   <li><b>碰撞概率极低</b>：122 位随机数，每毫秒可生成 2^122 个不重复 ID</li>
 *   <li><b>标准格式</b>：符合 RFC 9562（原 RFC 4122），与现有 UUID 工具兼容</li>
 * </ul>
 *
 * <h2>与 OpenTelemetry 的集成</h2>
 * <p>
 * Request ID 与 OpenTelemetry Trace ID 的关系：
 * </p>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                         Gateway (入口)                           │
 * │  ┌─────────────┐     ┌─────────────────────────────────────┐   │
 * │  │ RequestId   │────▶│ OpenTelemetry Span                  │   │
 * │  │ (UUID v7)   │     │ Trace ID: 128-bit W3C Trace Context  │   │
 * │  │             │     │ Span ID: 64-bit 操作标识             │   │
 * │  │ X-Request-ID│     │                                     │   │
 * │  │ Header      │     │ traceparent: 00-{trace}-{span}-01   │   │
 * │  └─────────────┘     └─────────────────────────────────────┘   │
 * │         │                              │                        │
 *         │                              │
 *         ▼                              ▼
 *  ┌─────────────┐              ┌─────────────────┐
 *  │ MDC         │              │ OTel Exporter   │
 *  │ request_id  │              │ → Jaeger/Tempo  │
 *  └─────────────┘              └─────────────────┘
 *         │
 *         ▼
 *  ┌─────────────────────────────────────────────────┐
 *  │ Logback/Log4j JSON 日志                         │
 *  │ {"request_id": "xxx", "trace_id": "yyy", ...}  │
 *  └─────────────────────────────────────────────────┘
 * </pre>
 *
 * <p>
 * 集成要点：
 * </p>
 * <ul>
 *   <li><b>MDC 透传</b>：request_id 存入 MDC 后，Logback 的 logstash-encoder 可自动提取</li>
 *   <li><b>Header 传递</b>：通过 X-Request-ID 头传递给下游服务，保持全链路一致</li>
 *   <li><b>OTel 关联</b>：在日志中同时记录 trace_id 和 request_id，支持双维度查询</li>
 *   <li><b>客户端支持</b>：优先使用客户端传入的 request_id，支持跨系统调用链串联</li>
 * </ul>
 *
 * <h2>使用示例</h2>
 * <pre>
 * // 客户端请求
 * GET /api/v1/agents
 * X-Request-ID: 018f3b2a-1c4d-7d8e-9f0a-1b2c3d4e5f6g
 *
 * // 服务端日志输出（自动包含 request_id）
 * {"timestamp":"2024-06-05T10:30:00Z","level":"INFO","request_id":"018f3b2a-...","message":"Request received"}
 *
 * // 下游服务收到的请求（Header 自动携带）
 * X-Request-ID: 018f3b2a-1c4d-7d8e-9f0a-1b2c3d4e5f6g
 * </pre>
 *
 * <h2>线程安全</h2>
 * <p>
 * MDC 基于 ThreadLocal 实现，每个请求线程拥有独立的 request_id 副本，
 * 不会产生线程安全问题。异步处理时需使用 MDC.getCopyOfContextMap() 手动传递。
 * </p>
 *
 * @see RequestIdGenerator Request ID 生成器（UUID v7 实现）
 * @see org.slf4j.MDC SLF4J MDC 机制
 * @see <a href="https://www.rfc-editor.org/rfc/rfc9562">RFC 9562 - UUIDs</a>
 */
@Slf4j
@Component
@Order(1)
public class RequestIdFilter implements Filter {

    /**
     * Request ID 请求头名称
     * <p>遵循 HTTP Header 命名惯例，使用 X- 前缀表示自定义头</p>
     */
    private static final String REQUEST_ID_HEADER = "X-Request-ID";

    /**
     * Trace ID 请求头名称（用于 OpenTelemetry 集成）
     * <p>W3C Trace Context 标准定义的 traceparent 头</p>
     */
    private static final String TRACE_ID_HEADER = "X-Trace-ID";

    /**
     * 过滤器核心逻辑：生成或传递 Request ID
     *
     * <p>处理流程：</p>
     * <ol>
     *   <li>检查请求头中是否存在 X-Request-ID</li>
     *   <li>若存在则复用，否则生成新的 UUID v7</li>
     *   <li>将 request_id 存入 MDC 供日志框架使用</li>
     *   <li>将 request_id 写入响应头，供客户端追踪</li>
     *   <li>请求结束后清理 MDC，防止内存泄漏</li>
     * </ol>
     *
     * @param request  Servlet 请求
     * @param response Servlet 响应
     * @param chain    过滤器链
     * @throws IOException      IO 异常
     * @throws ServletException Servlet 异常
     */
    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;

        // 优先使用客户端传入的 request_id，否则生成新的
        // 这样可以支持跨系统的调用链串联
        String requestId = httpRequest.getHeader(REQUEST_ID_HEADER);
        if (requestId == null || requestId.isBlank()) {
            requestId = RequestIdGenerator.generate();
        }

        // 设置到 MDC，使日志框架自动获取 request_id
        RequestIdGenerator.setCurrent(requestId);

        // 传递给下游服务和客户端
        if (response instanceof jakarta.servlet.http.HttpServletResponse) {
            jakarta.servlet.http.HttpServletResponse httpResponse =
                    (jakarta.servlet.http.HttpServletResponse) response;
            httpResponse.setHeader(REQUEST_ID_HEADER, requestId);
        }

        try {
            chain.doFilter(request, response);
        } finally {
            // 清理 MDC，防止线程复用时数据污染
            RequestIdGenerator.clear();
        }
    }
}
