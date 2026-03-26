package com.platform.gateway.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.IOException;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class ApiKeyAuthenticationFilterTest {

    @InjectMocks
    private ApiKeyAuthenticationFilter filter;

    private MockHttpServletRequest request;
    private MockHttpServletResponse response;
    private FilterChain filterChain;

    @BeforeEach
    void setUp() {
        request = new MockHttpServletRequest();
        response = new MockHttpServletResponse();
        filterChain = mock(FilterChain.class);
        SecurityContextHolder.clearContext();
        ReflectionTestUtils.setField(filter, "apiKeyEnabled", true);
    }

    @Test
    void shouldSkipPublicEndpoints() throws ServletException, IOException {
        request.setRequestURI("/health");

        filter.doFilterInternal(request, response, filterChain);

        verify(filterChain).doFilter(request, response);
        assertNull(SecurityContextHolder.getContext().getAuthentication());
    }

    @Test
    void shouldSkipWhenApiKeyDisabled() throws ServletException, IOException {
        ReflectionTestUtils.setField(filter, "apiKeyEnabled", false);
        request.setRequestURI("/api/v1/chat");

        filter.doFilterInternal(request, response, filterChain);

        verify(filterChain).doFilter(request, response);
    }

    @Test
    void shouldAuthenticateWithServiceKey() throws ServletException, IOException {
        String apiKey = "svc_test_key";
        request.setRequestURI("/api/v1/chat");
        request.addHeader("X-API-Key", apiKey);

        ReflectionTestUtils.setField(filter, "serviceApiKey", "svc_test_key");

        filter.doFilterInternal(request, response, filterChain);

        verify(filterChain).doFilter(request, response);
        assertNotNull(SecurityContextHolder.getContext().getAuthentication());
    }

    @Test
    void shouldRejectInvalidApiKey() throws ServletException, IOException {
        String apiKey = "invalid_key";
        request.setRequestURI("/api/v1/chat");
        request.addHeader("X-API-Key", apiKey);

        filter.doFilterInternal(request, response, filterChain);

        assertEquals(HttpServletResponse.SC_UNAUTHORIZED, response.getStatus());
    }
}