package com.platform.gateway.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import jakarta.servlet.DispatcherType;
import java.io.IOException;
import java.util.List;

/**
 * 开发环境认证过滤器
 *
 * 【用途】
 * 在开发环境下，允许通过 X-Tenant-ID 和 X-User-ID header 绕过认证，
 * 方便前端开发和测试。
 *
 * 【安全说明】
 * - 仅在 auth.dev-bypass.enabled=true 时启用
 * - 生产环境必须禁用此功能
 * - 通过检查 spring.profiles.active 确保只在开发环境生效
 *
 * 【请求头】
 * - X-Tenant-ID: 租户ID
 * - X-User-ID: 用户ID
 */
@Slf4j
@Component
public class DevAuthenticationFilter extends OncePerRequestFilter {

    private static final String TENANT_ID_HEADER = "X-Tenant-ID";
    private static final String USER_ID_HEADER = "X-User-ID";

    @Value("${auth.dev-bypass.enabled:false}")
    private boolean devBypassEnabled;

    @Value("${spring.profiles.active:prod}")
    private String activeProfile;

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain
    ) throws ServletException, IOException {

        // ASYNC 分发时跳过：SecurityContext 已通过 MODE_INHERITABLETHREADLOCAL 传播，
        // 且异步线程的 ClassLoader 可能无法加载自定义 Principal 类
        if (request.getDispatcherType() == DispatcherType.ASYNC) {
            filterChain.doFilter(request, response);
            return;
        }

        // 如果已有认证，跳过
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            filterChain.doFilter(request, response);
            return;
        }

        // 检查是否启用开发模式绕过
        if (!isDevBypassEnabled()) {
            filterChain.doFilter(request, response);
            return;
        }

        String requestPath = request.getRequestURI();

        // 跳过公开端点
        if (isPublicEndpoint(requestPath)) {
            filterChain.doFilter(request, response);
            return;
        }

        // 提取开发环境 header
        String tenantId = request.getHeader(TENANT_ID_HEADER);
        String userId = request.getHeader(USER_ID_HEADER);

        // 开发模式下，如果没有 header 则使用默认值
        if (!StringUtils.hasText(tenantId)) {
            tenantId = "tenant_001"; // 开发环境默认租户
        }
        if (!StringUtils.hasText(userId)) {
            userId = "user_001"; // 开发环境默认用户
        }

        log.debug("Dev authentication: userId={}, tenantId={}, path={}",
            userId, tenantId, requestPath);

        // 构建开发环境认证
        UserPrincipal principal = new UserPrincipal(userId, "dev_user", tenantId);

        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                principal,
                null,
                List.of(
                    new SimpleGrantedAuthority("ROLE_USER"),
                    new SimpleGrantedAuthority("ROLE_OPERATOR")
                )
        );

        SecurityContextHolder.getContext().setAuthentication(authentication);

        // 设置请求属性
        request.setAttribute("tenantId", tenantId);
        request.setAttribute("userId", userId);

        filterChain.doFilter(request, response);
    }

    /**
     * 判断是否启用开发模式绕过
     */
    private boolean isDevBypassEnabled() {
        // 必须同时满足：
        // 1. 配置启用
        // 2. 不是生产环境
        return devBypassEnabled &&
               !"prod".equals(activeProfile) &&
               !"production".equals(activeProfile);
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
}
