package com.platform.gateway.service;

import com.platform.gateway.dto.request.LoginRequest;
import com.platform.gateway.dto.request.RefreshTokenRequest;
import com.platform.gateway.dto.response.LoginResponse;
import com.platform.gateway.dto.response.RefreshTokenResponse;
import com.platform.gateway.entity.TenantUser;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.TenantUserRepository;
import com.platform.gateway.util.JwtUtil;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("AuthService 测试")
class AuthServiceTest {

    @Mock
    private TenantUserRepository userRepository;

    @Mock
    private JwtUtil jwtUtil;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private StringRedisTemplate redisTemplate;

    @Mock
    private ValueOperations<String, String> valueOperations;

    @InjectMocks
    private AuthService authService;

    private TenantUser testUser;
    private LoginRequest loginRequest;

    @BeforeEach
    void setUp() {
        testUser = new TenantUser();
        testUser.setId("user-123");
        testUser.setUsername("admin");
        testUser.setPasswordHash("$2a$10$encodedPassword");
        testUser.setTenantId("tenant-123");
        testUser.setEmail("admin@example.com");

        loginRequest = new LoginRequest();
        loginRequest.setUsername("admin");
        loginRequest.setPassword("password");
    }

    @Test
    @DisplayName("应该成功登录当凭证正确")
    void should_login_successfully_when_credentials_are_correct() {
        // Given
        when(userRepository.findByUsername("admin")).thenReturn(Optional.of(testUser));
        when(passwordEncoder.matches("password", "$2a$10$encodedPassword")).thenReturn(true);
        when(jwtUtil.generateAccessToken(anyMap())).thenReturn("access-token");
        when(jwtUtil.generateRefreshToken(anyMap())).thenReturn("refresh-token");
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);

        // When
        LoginResponse response = authService.login(loginRequest);

        // Then
        assertNotNull(response);
        assertEquals("access-token", response.getTokens().getAccessToken());
        assertEquals("refresh-token", response.getTokens().getRefreshToken());
        assertNotNull(response.getUser());
        assertNotNull(response.getTenant());
    }

    @Test
    @DisplayName("应该抛出异常当用户不存在")
    void should_throw_exception_when_user_not_found() {
        // Given
        when(userRepository.findByUsername("nonexistent")).thenReturn(Optional.empty());

        LoginRequest request = new LoginRequest();
        request.setUsername("nonexistent");
        request.setPassword("password");

        // When & Then
        assertThrows(BusinessException.class, () -> authService.login(request));
    }

    @Test
    @DisplayName("应该抛出异常当密码错误")
    void should_throw_exception_when_password_is_incorrect() {
        // Given
        when(userRepository.findByUsername("admin")).thenReturn(Optional.of(testUser));
        when(passwordEncoder.matches("wrong-password", "$2a$10$encodedPassword")).thenReturn(false);

        LoginRequest request = new LoginRequest();
        request.setUsername("admin");
        request.setPassword("wrong-password");

        // When & Then
        assertThrows(BusinessException.class, () -> authService.login(request));
    }

    @Test
    @DisplayName("应该刷新 Token 当 Refresh Token 有效")
    void should_refresh_token_when_refresh_token_is_valid() {
        // Given
        RefreshTokenRequest request = new RefreshTokenRequest();
        request.setRefreshToken("valid-refresh-token");

        when(redisTemplate.hasKey("refresh:valid-refresh-token")).thenReturn(true);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
        when(valueOperations.get("refresh:valid-refresh-token")).thenReturn("user-123");
        when(userRepository.findById("user-123")).thenReturn(Optional.of(testUser));
        when(jwtUtil.generateAccessToken(anyMap())).thenReturn("new-access-token");
        when(jwtUtil.generateRefreshToken(anyMap())).thenReturn("new-refresh-token");

        // When
        RefreshTokenResponse response = authService.refreshToken(request);

        // Then
        assertNotNull(response);
        assertEquals("new-access-token", response.getAccessToken());
        assertEquals("new-refresh-token", response.getRefreshToken());
    }

    @Test
    @DisplayName("应该抛出异常当 Refresh Token 无效")
    void should_throw_exception_when_refresh_token_is_invalid() {
        // Given
        RefreshTokenRequest request = new RefreshTokenRequest();
        request.setRefreshToken("invalid-refresh-token");

        when(redisTemplate.hasKey("refresh:invalid-refresh-token")).thenReturn(false);

        // When & Then
        assertThrows(BusinessException.class, () -> authService.refreshToken(request));
    }

    @Test
    @DisplayName("应该成功登出")
    void should_logout_successfully() {
        // Given
        String userId = "user-123";
        when(redisTemplate.delete(anyString())).thenReturn(true);

        // When
        authService.logout(userId);

        // Then
        verify(redisTemplate, times(1)).delete(anyString());
    }
}
