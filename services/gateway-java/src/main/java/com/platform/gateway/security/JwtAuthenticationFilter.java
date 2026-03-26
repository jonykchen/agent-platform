package com.platform.gateway.security;

import com.platform.gateway.util.JwtUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Arrays;
import java.util.stream.Collectors;

/**
 * JWT 认证过滤器
 *
 * 【认证流程】
 * 1. 从请求头提取 Authorization: Bearer <token>
 * 2. 验证 Token 签名和有效期
 * 3. 解析用户信息（userId, tenantId, roles）
 * 4. 设置 Spring Security Context
 * 5. 继续过滤器链
 *
 * 【安全注意事项】
 * - Token 失效时返回 401，不暴露具体原因
 * - 使用 HMAC-SHA256 签名验证
 * - 支持 Token 刷新机制
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtUtil jwtUtil;

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {

        String requestPath = request.getRequestURI();

        // 跳过公开端点
        if (isPublicEndpoint(requestPath)) {
            filterChain.doFilter(request, response);
            return;
        }

        // 提取 Token
        String token = extractToken(request);

        if (token == null) {
            // 无 Token，继续到下一个过滤器（可能是 API Key 认证）
            filterChain.doFilter(request, response);
            return;
        }

        // 验证 Token
        if (!jwtUtil.validateToken(token)) {
            log.warn("JWT validation failed for path: {}", requestPath);
            sendUnauthorizedResponse(response, "Invalid token");
            return;
        }

        // 提取用户信息
        String userId = jwtUtil.extractUserId(token);
        String username = jwtUtil.extractUsername(token);
        String tenantId = jwtUtil.extractTenantId(token);
        String[] roles = jwtUtil.extractRoles(token);

        // 构建 Authentication 对象
        UserPrincipal principal = new UserPrincipal(userId, username, tenantId);

        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                principal,
                null,
                Arrays.stream(roles)
                    .map(role -> new SimpleGrantedAuthority("ROLE_" + role))
                    .collect(Collectors.toList())
        );

        // 设置 Security Context
        SecurityContextHolder.getContext().setAuthentication(authentication);

        // 设置租户上下文（用于多租户隔离）
        request.setAttribute("tenantId", tenantId);
        request.setAttribute("userId", userId);

        log.debug("JWT authentication successful: userId={}, tenantId={}", userId, tenantId);

        filterChain.doFilter(request, response);
    }

    /**
     * 从请求头提取 Token
     */
    private String extractToken(HttpServletRequest request) {
        String authHeader = request.getHeader(AUTHORIZATION_HEADER);

        if (StringUtils.hasText(authHeader) && authHeader.startsWith(BEARER_PREFIX)) {
            return authHeader.substring(BEARER_PREFIX.length());
        }

        return null;
    }

    /**
     * 判断是否为公开端点
     */
    private boolean isPublicEndpoint(String path) {
        return path.startsWith("/health") ||
               path.startsWith("/ready") ||
               path.startsWith("/actuator/") ||
               path.equals("/api/v1/auth/login") ||
               path.equals("/api/v1/auth/refresh");
    }

    /**
     * 发送 401 响应
     */
    private void sendUnauthorizedResponse(HttpServletResponse response, String message) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(String.format(
            "{\"error\":\"ERR_UNAUTHORIZED\",\"message\":\"%s\"}",
            message
        ));
    }
}