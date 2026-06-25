package com.platform.governance.config;

import com.platform.governance.security.ServiceTokenAuthenticationFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

/**
 * Governance 服务安全配置
 *
 * <p>启用方法级安全（{@code @PreAuthorize}），配置 HTTP 安全过滤链：
 * <ul>
 *   <li>内部服务调用通过 Service Token 认证</li>
 *   <li>Actuator 健康检查端点公开访问</li>
 *   <li>其他端点需要认证</li>
 * </ul>
 *
 * <h3>认证方式</h3>
 * <ul>
 *   <li><b>Service Token</b>：内部服务间调用，通过 {@code X-Service-Token} 头传递</li>
 *   <li><b>JWT</b>：外部调用经 Gateway 代理后，JWT 信息由 Gateway 传递</li>
 * </ul>
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    @Value("${service.auth.secret:}")
    private String serviceAuthSecret;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                // Actuator 健康检查公开
                .requestMatchers("/actuator/health", "/actuator/info").permitAll()
                // API 端点需要认证
                .requestMatchers("/api/v1/**").authenticated()
                // 其他请求需要认证
                .anyRequest().authenticated()
            )
            .addFilterBefore(
                new ServiceTokenAuthenticationFilter(serviceAuthSecret),
                UsernamePasswordAuthenticationFilter.class
            );

        return http.build();
    }
}
