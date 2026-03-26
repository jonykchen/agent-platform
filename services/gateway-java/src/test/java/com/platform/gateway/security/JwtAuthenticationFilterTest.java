package com.platform.gateway.security;

import com.platform.gateway.util.JwtUtil;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.context.SecurityContextHolder;

import java.io.IOException;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class JwtAuthenticationFilterTest {

    @Mock
    private JwtUtil jwtUtil;

    @InjectMocks
    private JwtAuthenticationFilter filter;

    private MockHttpServletRequest request;
    private MockHttpServletResponse response;
    private FilterChain filterChain;

    @BeforeEach
    void setUp() {
        request = new MockHttpServletRequest();
        response = new MockHttpServletResponse();
        filterChain = mock(FilterChain.class);
        SecurityContextHolder.clearContext();
    }

    @Test
    void shouldSkipPublicEndpoints() throws ServletException, IOException {
        request.setRequestURI("/health");

        filter.doFilterInternal(request, response, filterChain);

        verify(filterChain).doFilter(request, response);
        assertNull(SecurityContextHolder.getContext().getAuthentication());
    }

    @Test
    void shouldContinueWhenNoToken() throws ServletException, IOException {
        request.setRequestURI("/api/v1/chat");
        request.addHeader("Authorization", "");

        filter.doFilterInternal(request, response, filterChain);

        verify(filterChain).doFilter(request, response);
    }

    @Test
    void shouldAuthenticateWithValidToken() throws ServletException, IOException {
        String token = "valid.jwt.token";
        request.setRequestURI("/api/v1/chat");
        request.addHeader("Authorization", "Bearer " + token);

        when(jwtUtil.validateToken(token)).thenReturn(true);
        when(jwtUtil.extractUserId(token)).thenReturn("user_001");
        when(jwtUtil.extractUsername(token)).thenReturn("testuser");
        when(jwtUtil.extractTenantId(token)).thenReturn("tenant_001");
        when(jwtUtil.extractRoles(token)).thenReturn(new String[]{"admin"});

        filter.doFilterInternal(request, response, filterChain);

        verify(filterChain).doFilter(request, response);
        assertNotNull(SecurityContextHolder.getContext().getAuthentication());
        assertEquals("user_001", ((UserPrincipal) SecurityContextHolder.getContext()
            .getAuthentication().getPrincipal()).getUserId());
    }

    @Test
    void shouldRejectInvalidToken() throws ServletException, IOException {
        String token = "invalid.token";
        request.setRequestURI("/api/v1/chat");
        request.addHeader("Authorization", "Bearer " + token);

        when(jwtUtil.validateToken(token)).thenReturn(false);

        filter.doFilterInternal(request, response, filterChain);

        assertEquals(HttpServletResponse.SC_UNAUTHORIZED, response.getStatus());
        verify(filterChain, never()).doFilter(request, response);
    }
}