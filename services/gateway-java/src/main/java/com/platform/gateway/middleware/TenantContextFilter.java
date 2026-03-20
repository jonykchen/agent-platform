package com.platform.gateway.middleware;

import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.TenantContextService;
import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.io.IOException;

/**
 * 租户上下文过滤器
 * 从 Header 提取 tenant_id 和 user_id
 */
@Slf4j
@Component
@Order(2)
@RequiredArgsConstructor
public class TenantContextFilter implements Filter {

    private static final String TENANT_ID_HEADER = "X-Tenant-ID";
    private static final String USER_ID_HEADER = "X-User-ID";

    private final TenantContextService tenantContextService;

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;

        // 提取 tenant_id
        String tenantId = httpRequest.getHeader(TENANT_ID_HEADER);
        if (tenantId == null || tenantId.isBlank()) {
            // 允许健康检查等路径跳过租户检查
            String path = httpRequest.getRequestURI();
            if (path.startsWith("/health") || path.startsWith("/ready") || path.startsWith("/actuator")) {
                chain.doFilter(request, response);
                return;
            }
            log.warn("Missing tenant_id header");
            throw BusinessException.of(ErrorCode.ERR_INVALID_REQUEST, "Missing X-Tenant-ID header");
        }

        // 提取 user_id（可选）
        String userId = httpRequest.getHeader(USER_ID_HEADER);
        if (userId == null || userId.isBlank()) {
            userId = "anonymous";
        }

        // 设置租户上下文
        tenantContextService.setCurrentTenant(tenantId, userId);

        try {
            chain.doFilter(request, response);
        } finally {
            tenantContextService.clear();
        }
    }
}