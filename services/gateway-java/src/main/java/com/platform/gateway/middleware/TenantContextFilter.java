package com.platform.gateway.middleware;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.dto.response.ErrorResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.Order;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

/**
 * 租户上下文过滤器
 * 从 Header 提取 tenant_id, user_id 和 request_id
 *
 * 【核心概念】多租户隔离原理
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * 多租户 SaaS 系统必须隔离租户数据，防止：
 * - 租户 A 访问租户 B 的数据
 * - 跨租户数据泄露
 * - 配额/权限混乱
 *
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          租户隔离层级                                        │
 * │                                                                             │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  L1: Filter 层隔离 (本模块)                                       │    │
 * │   │  - 从 Header 提取 tenant_id                                       │    │
 * │   │  - 存入 ThreadLocal                                               │    │
 * │   │  - 确保后续代码可获取                                              │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  L2: Service 层隔离                                               │    │
 * │   │  - 查询时自动添加 tenant_id 条件                                  │    │
 * │   │  - @TenantAware 注解                                              │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │   ┌──────────────────────────────────────────────────────────────────┐    │
 * │   │  L3: 数据库层隔离                                                 │    │
 * │   │  - 所有表有 tenant_id 列                                          │    │
 * │   │  - 外键关联包含 tenant_id                                         │    │
 * │   └──────────────────────────────────────────────────────────────────┘    │
 * │                          │                                                  │
 * │                          ▼                                                  │
 * │                      安全的租户隔离                                          │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *
 * 【技术选型】上下文传播方案
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ ThreadLocal (选择) │ • 线程隔离，自动传播        │ • 需注意清理                │
 * │                    │ • 无需手动传递参数          │ • 异步场景需特殊处理        │
 * │                    │ • Spring 生态支持           │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Request Attribute  │ • 简单                      │ • 跨服务传播需手动          │
 * │                    │                             │ • 每次获取需 request 对象   │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ Context Propagation│ • 标准化                    │ • 额外依赖                  │
 * │ (Micrometer)       │ • 跨服务自动传播            │ • 配置复杂                  │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【选择 ThreadLocal 的原因】
 * 1. Spring 生态原生支持（RequestContextHolder）
 * 2. 无需修改 Service 方法签名
 * 3. 性能好：无网络开销
 *
 * 【Filter 执行顺序】
 * - @Order(1): RequestIdFilter（生成 request_id）
 * - @Order(2): TenantContextFilter（本模块，提取 tenant_id）
 * - @Order(3): AuthFilter（可选，JWT 验证）
 *
 * 【注意事项】
 * - 必须在 finally 中清理 ThreadLocal，防止线程复用时数据泄露
 * - 健康检查等路径可跳过租户检查（path.startsWith("/health")）
 */
@Slf4j
@Component
@Order(2)
@RequiredArgsConstructor
public class TenantContextFilter implements Filter {

    private static final String TENANT_ID_HEADER = "X-Tenant-ID";
    private static final String USER_ID_HEADER = "X-User-ID";
    private static final String REQUEST_ID_HEADER = "X-Request-ID";

    private final TenantContextService tenantContextService;
    private final ObjectMapper objectMapper;

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        // 提取 tenant_id
        String tenantId = httpRequest.getHeader(TENANT_ID_HEADER);
        if (tenantId == null || tenantId.isBlank()) {
            // 允许健康检查、认证路径和公开 API 跳过租户检查
            String path = httpRequest.getRequestURI();
            if (isPublicPath(path)) {
                chain.doFilter(request, response);
                return;
            }
            log.warn("Missing tenant_id header");
            writeErrorResponse(httpResponse, ErrorCode.ERR_INVALID_REQUEST, "Missing X-Tenant-ID header");
            return;
        }

        // 提取 user_id（可选）
        String userId = httpRequest.getHeader(USER_ID_HEADER);
        if (userId == null || userId.isBlank()) {
            userId = "anonymous";
        }

        // 提取 request_id（可选）
        String requestId = httpRequest.getHeader(REQUEST_ID_HEADER);

        // 设置租户上下文
        tenantContextService.setCurrentTenant(tenantId, userId);
        if (requestId != null && !requestId.isBlank()) {
            tenantContextService.setCurrentRequestId(requestId);
        }

        try {
            chain.doFilter(request, response);
        } finally {
            tenantContextService.clear();
        }
    }

    /**
     * 判断是否为公开路径（无需租户上下文）
     *
     * @param path 请求路径
     * @return 是否为公开路径
     */
    private boolean isPublicPath(String path) {
        // 健康检查和监控端点
        if (path.startsWith("/health") || path.startsWith("/ready") || path.startsWith("/actuator")) {
            return true;
        }
        // 认证相关端点
        if (path.equals("/api/v1/auth/login") || path.equals("/api/v1/auth/refresh")
                || path.equals("/api/v1/auth/logout")) {
            return true;
        }
        // 公开 API：可用模型列表
        if (path.equals("/api/v1/tenants/models")) {
            return true;
        }
        return false;
    }

    /**
     * 写入错误响应（Filter 层异常处理）
     * Filter 中抛出的异常不会被 @RestControllerAdvice 捕获，需要手动处理
     */
    private void writeErrorResponse(HttpServletResponse response, ErrorCode errorCode, String message) throws IOException {
        response.setStatus(errorCode.getHttpStatus());
        response.setContentType(MediaType.APPLICATION_JSON_VALUE);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());

        ErrorResponse errorResponse = ErrorResponse.builder()
                .error(errorCode.getCode())
                .message(message)
                .userMessage(errorCode.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .build();

        response.getWriter().write(objectMapper.writeValueAsString(errorResponse));
    }
}