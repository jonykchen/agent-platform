package com.platform.gateway.config;

import com.platform.gateway.security.ApiKeyAuthenticationFilter;
import com.platform.gateway.security.JwtAuthenticationFilter;
import com.platform.gateway.security.DevAuthenticationFilter;
import jakarta.annotation.PostConstruct;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.List;

/**
 * Spring Security 配置
 *
 * 【认证架构】
 * 多种认证方式并存：
 * 1. JWT Token: 用户登录后的会话认证
 * 2. API Key: 服务间调用或外部系统集成
 * 3. Dev Header: 开发环境通过 X-Tenant-ID/X-User-ID header 绕过认证
 *
 * 【过滤器链顺序】
 * Request → DevFilter → JwtFilter → ApiKeyFilter → ... → Controller
 *
 * 【授权规则】
 * - 公开端点: /health, /actuator, /auth/login
 * - 用户端点: 需要 JWT 认证
 * - 服务端点: 需要 API Key 或 JWT
 * - 开发环境: 允许 Dev Header 绕过认证
 *
 * 【异步安全上下文】
 * Gateway 使用 Servlet + WebFlux 混合架构，Controller 返回 Mono/Flux 时，
 * Spring MVC 会将请求转为异步模式（DeferredResult），触发 ASYNC 分发。
 *
 * ASYNC 分发时 Filter Chain 会重新执行，如果 SecurityContext 已被
 * SecurityContextHolderFilter 在初始请求完成时清理，则 AuthorizationFilter
 * 检测到无认证 → 403 Forbidden。
 *
 * 解决方案：
 * 1. 自定义 RequestAttributeSecurityContextRepository：将 SecurityContext 存储在
 *    request attribute 中，ASYNC 分发时从 attribute 恢复，避免上下文丢失
 * 2. MODE_INHERITABLETHREADLOCAL：作为额外的安全网，确保 Reactor 线程能获取上下文
 * 3. 认证 Filter 在 ASYNC 分发时跳过：避免重复认证和 ClassLoader 问题
 */
@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final ApiKeyAuthenticationFilter apiKeyAuthenticationFilter;
    private final DevAuthenticationFilter devAuthenticationFilter;

    /**
     * CORS 允许的来源列表。
     *
     * <p>从配置 {@code app.cors.allowed-origins} 读取（逗号分隔）。
     * 默认值仅包含本地开发端口；生产环境必须通过环境变量
     * {@code CORS_ALLOWED_ORIGINS} 显式指定可信域名白名单，禁止通配符。
     */
    @Value("${app.cors.allowed-origins:http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:5174,http://127.0.0.1:5175,http://127.0.0.1:3000}")
    private List<String> allowedOrigins;

    /**
     * 初始化 SecurityContext 策略为可继承线程本地变量。
     */
    @PostConstruct
    public void initSecurityContextHolderStrategy() {
        SecurityContextHolder.setStrategyName(SecurityContextHolder.MODE_INHERITABLETHREADLOCAL);
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                // 启用 CORS（使用上面定义的 corsConfigurationSource）
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))

                // 禁用 CSRF（无状态 REST API）
                .csrf(AbstractHttpConfigurer::disable)

                // 无状态会话
                .sessionManagement(session -> session
                        .sessionCreationPolicy(SessionCreationPolicy.STATELESS))

                // 使用 request attribute 存储 SecurityContext，确保 ASYNC 分发时可用
                .securityContext(securityContext -> securityContext
                        .securityContextRepository(new RequestAttributeSecurityContextRepository()))

                // 授权规则
                .authorizeHttpRequests(auth -> auth
                        // CORS 预检请求公开
                        .requestMatchers(org.springframework.http.HttpMethod.OPTIONS, "/**").permitAll()
                        // 健康检查端点公开
                        .requestMatchers("/health", "/ready", "/actuator/**").permitAll()
                        // 认证端点公开
                        .requestMatchers("/api/v1/auth/login", "/api/v1/auth/refresh").permitAll()
                        // 内部管理接口 - 开发环境允许访问
                        .requestMatchers("/api/v1/internal/**").permitAll()
                        // API 端点需要认证
                        .requestMatchers("/api/**").authenticated()
                        // 其他请求
                        .anyRequest().permitAll()
                )

                // 添加开发环境过滤器（最高优先级）
                .addFilterBefore(devAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)

                // 添加 JWT 过滤器（在 UsernamePasswordAuthenticationFilter 之前）
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)

                // 添加 API Key 过滤器（在 JWT 过滤器之后）
                .addFilterAfter(apiKeyAuthenticationFilter, JwtAuthenticationFilter.class);

        return http.build();
    }

    /**
     * 基于 Request Attribute 的 SecurityContextRepository。
     *
     * <p>将 SecurityContext 存储在 HttpServletRequest 的 attribute 中，
     * 解决 Servlet ASYNC 分发时 SecurityContext 丢失的问题。
     *
     * <p>工作原理：
     * <ol>
     *   <li>初始请求：认证 Filter 设置 SecurityContext 后，SecurityContextHolderFilter
     *       调用 saveContext() 将其保存到 request attribute</li>
     *   <li>ASYNC 分发：SecurityContextHolderFilter 调用 loadContext() 从 request attribute
     *       恢复 SecurityContext，AuthorizationFilter 检测到认证 → 放行</li>
     *   <li>request attribute 在同一请求的 REQUEST/ASYNC/ERROR 分发间共享</li>
     * </ol>
     *
     * <p>相比默认的 NullSecurityContextRepository（STATELESS 模式），不会丢失上下文；
     * 相比 HttpSessionSecurityContextRepository，不会创建 Session。
     */
    static class RequestAttributeSecurityContextRepository implements SecurityContextRepository {

        private static final String ATTR_KEY = "SPRING_SECURITY_CONTEXT";

        @Override
        public SecurityContext loadContext(org.springframework.security.web.context.HttpRequestResponseHolder requestResponse) {
            HttpServletRequest request = requestResponse.getRequest();
            SecurityContext context = (SecurityContext) request.getAttribute(ATTR_KEY);
            if (context == null) {
                context = SecurityContextHolder.createEmptyContext();
            }
            return context;
        }

        @Override
        public void saveContext(SecurityContext context, HttpServletRequest request,
                               HttpServletResponse response) {
            if (context.getAuthentication() != null) {
                request.setAttribute(ATTR_KEY, context);
            }
        }

        @Override
        public boolean containsContext(HttpServletRequest request) {
            return request.getAttribute(ATTR_KEY) != null;
        }
    }

    /**
     * CORS 配置源（全局唯一）
     *
     * <p>本应用 CORS 策略的<b>唯一来源</b>。历史上曾存在 SimpleCorsFilter、
     * WebCorsConfig、CorsFilterConfig 三处重复且不一致的配置，已全部删除，
     * 统一收敛到此处，避免预检请求绕过安全白名单。
     *
     * <p>允许来源由 {@link #allowedOrigins} 从配置注入，生产环境禁止通配符。
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration config = new CorsConfiguration();

        // 允许的来源（从配置读取，使用精确 allowedOrigins，不使用通配符 pattern）
        config.setAllowedOrigins(allowedOrigins);

        // 允许的方法
        config.setAllowedMethods(List.of("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));

        // 允许的请求头
        config.setAllowedHeaders(List.of("*"));

        // 允许携带凭证
        config.setAllowCredentials(true);

        // 暴露的响应头
        config.setExposedHeaders(List.of("X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"));

        // 预检请求缓存时间
        config.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);

        return source;
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
