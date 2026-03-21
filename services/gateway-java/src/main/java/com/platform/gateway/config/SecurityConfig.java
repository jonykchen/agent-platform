package com.platform.gateway.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Spring Security 配置
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

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
                );

        // TODO: 添加 JWT 过滤器和 API Key 认证
        // 当前 Phase 1 MVP 允许所有请求通过（依赖网关层的租户隔离）

        return http.build();
    }
}