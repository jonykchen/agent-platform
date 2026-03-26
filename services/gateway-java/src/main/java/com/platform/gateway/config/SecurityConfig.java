package com.platform.gateway.config;

import com.platform.gateway.security.ApiKeyAuthenticationFilter;
import com.platform.gateway.security.JwtAuthenticationFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * Spring Security 配置
 *
 * 【认证架构】
 * 多种认证方式并存：
 * 1. JWT Token: 用户登录后的会话认证
 * 2. API Key: 服务间调用或外部系统集成
 *
 * 【过滤器链顺序】
 * Request → JwtFilter → ApiKeyFilter → ... → Controller
 *
 * 【授权规则】
 * - 公开端点: /health, /actuator, /auth/login
 * - 用户端点: 需要 JWT 认证
 * - 服务端点: 需要 API Key 或 JWT
 */
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final ApiKeyAuthenticationFilter apiKeyAuthenticationFilter;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                // 禁用 CSRF（无状态 REST API）
                .csrf(AbstractHttpConfigurer::disable)

                // 无状态会话
                .sessionManagement(session -> session
                        .sessionCreationPolicy(SessionCreationPolicy.STATELESS))

                // 授权规则
                .authorizeHttpRequests(auth -> auth
                        // 健康检查端点公开
                        .requestMatchers("/health", "/ready", "/actuator/**").permitAll()
                        // 认证端点公开
                        .requestMatchers("/api/v1/auth/login", "/api/v1/auth/refresh").permitAll()
                        // API 端点需要认证
                        .requestMatchers("/api/**").authenticated()
                        // 其他请求
                        .anyRequest().permitAll()
                )

                // 添加 JWT 过滤器（在 UsernamePasswordAuthenticationFilter 之前）
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)

                // 添加 API Key 过滤器（在 JWT 过滤器之后）
                .addFilterAfter(apiKeyAuthenticationFilter, JwtAuthenticationFilter.class);

        return http.build();
    }

    /**
     * 密码编码器
     * 使用 BCrypt 算法
     */
    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}