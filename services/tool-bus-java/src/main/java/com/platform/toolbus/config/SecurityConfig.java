package com.platform.toolbus.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * ToolBus Spring Security 配置
 *
 * <p>最小化安全配置：
 * <ul>
 *   <li>gRPC 端点由 {@link com.platform.toolbus.grpc.AuthServerInterceptor} 独立认证</li>
 *   <li>HTTP 管理端点 (/internal/tools) 由 @PreAuthorize 保护</li>
 *   <li>Actuator/health 端点公开</li>
 * </ul>
 *
 * <p>认证方式：ToolBus 在 Gateway 之后，由 Gateway 注入 X-Service-Role Header 标识调用方身份。
 * 开发环境可通过 dev profile 绕过。
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final ServiceRoleAuthenticationFilter serviceRoleAuthenticationFilter;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session
                .sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                // 健康检查和 actuator 端点公开
                .requestMatchers("/health", "/actuator/**").permitAll()
                // 其他所有请求需要认证
                .anyRequest().authenticated()
            )
            // 通过 DI 注入 filter（支持 @Value 配置注入和 HMAC 签名验证）
            .addFilterBefore(serviceRoleAuthenticationFilter,
                UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
