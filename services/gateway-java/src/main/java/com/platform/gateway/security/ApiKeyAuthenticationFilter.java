package com.platform.gateway.security;

import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.ApiKeyService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * API Key 认证过滤器
 *
 * 【用途】
 * 用于服务间调用或外部系统集成的认证：
 * - 内部微服务调用（如 Orchestrator → Gateway）
 * - 外部 API 集成（如企业系统对接）
 * - CI/CD 自动化调用
 *
 * 【认证流程】
 * 1. 从请求头提取 X-API-Key
 * 2. 验证 API Key 有效性和权限
 * 3. 解析租户信息
 * 4. 设置 Security Context
 *
 * 【API Key 格式】
 * 前缀标识类型：
 * - svc_: 服务间调用
 * - ext_: 外部系统集成
 * - test_: 测试环境
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class ApiKeyAuthenticationFilter extends OncePerRequestFilter {

    private static final String API_KEY_HEADER = "X-API-Key";

    private final ApiKeyService apiKeyService;

    @Value("${auth.api-key.header:X-API-Key}")
    private String apiKeyHeader;

    @Value("${auth.api-key.service-key:}")
    private String serviceApiKey;

    @Value("${auth.api-key.enabled:false}")
    private boolean apiKeyEnabled;

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {

        // 如果已有 JWT 认证，跳过 API Key 认证
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            filterChain.doFilter(request, response);
            return;
        }

        String requestPath = request.getRequestURI();

        // 跳过公开端点
        if (isPublicEndpoint(requestPath)) {
            filterChain.doFilter(request, response);
            return;
        }

        // 如果 API Key 认证未启用，跳过
        if (!apiKeyEnabled) {
            filterChain.doFilter(request, response);
            return;
        }

        // 提取 API Key
        String apiKey = extractApiKey(request);

        if (apiKey == null) {
            filterChain.doFilter(request, response);
            return;
        }

        // 验证 API Key
        ApiKeyPrincipal principal = validateApiKey(apiKey);

        if (principal == null) {
            log.warn("API Key validation failed for path: {}", requestPath);
            sendUnauthorizedResponse(response, "Invalid API key");
            return;
        }

        // 构建 Authentication
        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                principal,
                null,
                principal.getAuthorities()
        );

        SecurityContextHolder.getContext().setAuthentication(authentication);

        // 设置租户上下文
        request.setAttribute("tenantId", principal.getTenantId());
        request.setAttribute("userId", principal.getUserId());

        log.debug("API Key authentication successful: type={}, tenantId={}",
            principal.getType(), principal.getTenantId());

        filterChain.doFilter(request, response);
    }

    /**
     * 提取 API Key
     */
    private String extractApiKey(HttpServletRequest request) {
        String apiKey = request.getHeader(apiKeyHeader);

        if (!StringUtils.hasText(apiKey)) {
            // 也支持查询参数（某些场景需要）
            apiKey = request.getParameter("api_key");
        }

        return apiKey;
    }

    /**
     * 验证 API Key
     *
     * 【验证规则】
     * 1. 检查格式（前缀 + 密钥）
     * 2. 验证密钥有效性
     * 3. 解析权限范围
     */
    private ApiKeyPrincipal validateApiKey(String apiKey) {
        // 服务间调用
        if (apiKey.startsWith("svc_")) {
            return validateServiceKey(apiKey);
        }

        // 外部系统 - 数据库验证
        if (apiKey.startsWith("ext_")) {
            return apiKeyService.validateExternalKey(apiKey);
        }

        // 测试环境
        if (apiKey.startsWith("test_") && "local".equals(System.getProperty("env"))) {
            return validateTestKey(apiKey);
        }

        return null;
    }

    /**
     * 验证服务间调用 API Key
     */
    private ApiKeyPrincipal validateServiceKey(String apiKey) {
        if (serviceApiKey != null && apiKey.equals(serviceApiKey)) {
            return new ApiKeyPrincipal(
                "service",
                "internal_service",
                "system",
                java.util.List.of(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_SERVICE"))
            );
        }
        return null;
    }

    /**
     * 验证测试环境 API Key
     */
    private ApiKeyPrincipal validateTestKey(String apiKey) {
        return new ApiKeyPrincipal(
            "test",
            "test_user",
            "tenant_001",
            java.util.List.of(new org.springframework.security.core.authority.SimpleGrantedAuthority("ROLE_OPERATOR"))
        );
    }

    private boolean isPublicEndpoint(String path) {
        return path.startsWith("/health") ||
               path.startsWith("/ready") ||
               path.startsWith("/actuator/") ||
               path.equals("/api/v1/auth/login") ||
               path.equals("/api/v1/auth/refresh");
    }

    private void sendUnauthorizedResponse(HttpServletResponse response, String message) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(String.format(
            "{\"error\":\"ERR_UNAUTHORIZED\",\"message\":\"%s\"}",
            message
        ));
    }
}