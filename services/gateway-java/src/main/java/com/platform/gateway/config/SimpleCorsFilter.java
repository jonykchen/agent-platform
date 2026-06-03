package com.platform.gateway.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Set;

/**
 * 简单 CORS 过滤器
 *
 * <p>在 Spring Security 过滤器链之前处理 OPTIONS 预检请求，
 * 避免 Security 拦截 CORS 预检。
 *
 * <p>使用 @Order(Ordered.HIGHEST_PRECEDENCE) 确保这个过滤器最先执行。
 */
@Slf4j
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class SimpleCorsFilter extends OncePerRequestFilter {

    private static final Set<String> ALLOWED_ORIGINS = Set.of(
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://127.0.0.1:3000"
    );

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain filterChain)
            throws ServletException, IOException {

        String origin = request.getHeader("Origin");
        String requestMethod = request.getHeader("Access-Control-Request-Method");
        String requestHeaders = request.getHeader("Access-Control-Request-Headers");
        String requestMethodType = request.getMethod();

        log.debug("CORS request: origin={}, method={}, requestMethod={}, headers={}",
                origin, requestMethodType, requestMethod, requestHeaders);

        // 如果是 OPTIONS 预检请求，直接返回 CORS 响应
        if ("OPTIONS".equalsIgnoreCase(requestMethodType)) {
            if (origin != null && ALLOWED_ORIGINS.contains(origin)) {
                response.setHeader("Access-Control-Allow-Origin", origin);
                response.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS");
                response.setHeader("Access-Control-Allow-Headers", "*");
                response.setHeader("Access-Control-Allow-Credentials", "true");
                response.setHeader("Access-Control-Max-Age", "3600");
                response.setStatus(HttpServletResponse.SC_OK);
                log.debug("CORS preflight OK for origin: {}", origin);
                return;
            } else {
                log.warn("CORS preflight rejected for origin: {}", origin);
            }
        }

        // 对于非预检请求，设置 CORS 响应头
        if (origin != null && ALLOWED_ORIGINS.contains(origin)) {
            response.setHeader("Access-Control-Allow-Origin", origin);
            response.setHeader("Access-Control-Allow-Credentials", "true");
            response.setHeader("Access-Control-Expose-Headers", "X-Request-ID, X-RateLimit-Limit, X-RateLimit-Remaining");
        }

        filterChain.doFilter(request, response);
    }
}
