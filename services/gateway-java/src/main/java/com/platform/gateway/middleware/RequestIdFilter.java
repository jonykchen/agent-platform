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
 * Request ID 过滤器
 * 生成/传递 request_id (UUID v7)，全链路贯穿
 */
@Slf4j
@Component
@Order(1)
public class RequestIdFilter implements Filter {

    private static final String REQUEST_ID_HEADER = "X-Request-ID";
    private static final String TRACE_ID_HEADER = "X-Trace-ID";

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {

        HttpServletRequest httpRequest = (HttpServletRequest) request;

        // 优先使用客户端传入的 request_id，否则生成新的
        String requestId = httpRequest.getHeader(REQUEST_ID_HEADER);
        if (requestId == null || requestId.isBlank()) {
            requestId = RequestIdGenerator.generate();
        }

        // 设置到 MDC
        RequestIdGenerator.setCurrent(requestId);

        // 传递给下游服务
        if (response instanceof jakarta.servlet.http.HttpServletResponse) {
            jakarta.servlet.http.HttpServletResponse httpResponse =
                    (jakarta.servlet.http.HttpServletResponse) response;
            httpResponse.setHeader(REQUEST_ID_HEADER, requestId);
        }

        try {
            chain.doFilter(request, response);
        } finally {
            RequestIdGenerator.clear();
        }
    }
}