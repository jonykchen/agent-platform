package com.platform.toolbus.config;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

/**
 * Service Role 认证过滤器
 *
 * <p>验证内部服务间调用时通过 {@code X-Service-Role} 头传递的角色信息。
 * 增加了 HMAC 签名验证，防止伪造 Header 绕过认证。
 *
 * <h3>认证流程</h3>
 * <ol>
 *   <li>Gateway 在代理请求时，设置 X-Service-Role 和 X-Service-Signature 头</li>
 *   <li>X-Service-Role: 角色名称（如 SERVICE、APPROVER）</li>
 *   <li>X-Service-Signature: HMAC-SHA256(service_role:timestamp:shared_secret)</li>
 *   <li>X-Service-Timestamp: 请求时间戳（秒）</li>
 * </ol>
 *
 * <p>安全说明：此 Header 仅在内部网络可信（Gateway → ToolBus）。
 * 生产环境必须通过网络策略确保 ToolBus 的 HTTP 端口仅对 Gateway 可达。
 */
@Slf4j
@Component
public class ServiceRoleAuthenticationFilter extends OncePerRequestFilter {

    private static final String SERVICE_ROLE_HEADER = "X-Service-Role";
    private static final String SERVICE_SIGNATURE_HEADER = "X-Service-Signature";
    private static final String SERVICE_TIMESTAMP_HEADER = "X-Service-Timestamp";
    private static final long MAX_TIMESTAMP_AGE_SECONDS = 300; // 5 minutes
    private static final String HMAC_ALGORITHM = "HmacSHA256";

    @Value("${service.auth.secret:}")
    private String sharedSecret;

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain filterChain) throws ServletException, IOException {
        // 如果已有认证，跳过
        if (SecurityContextHolder.getContext().getAuthentication() != null) {
            filterChain.doFilter(request, response);
            return;
        }

        String serviceRole = request.getHeader(SERVICE_ROLE_HEADER);
        if (serviceRole != null && !serviceRole.isBlank()) {
            // 验证签名
            if (validateSignature(serviceRole, request)) {
                List<SimpleGrantedAuthority> authorities = List.of(
                    new SimpleGrantedAuthority("ROLE_" + serviceRole.toUpperCase())
                );

                UsernamePasswordAuthenticationToken authentication =
                    new UsernamePasswordAuthenticationToken(
                        "service:" + serviceRole, null, authorities
                    );
                SecurityContextHolder.getContext().setAuthentication(authentication);

                log.debug("Service authenticated: role={}", serviceRole);
            } else {
                log.warn("Invalid service signature for role: {}", serviceRole);
            }
        }

        filterChain.doFilter(request, response);
    }

    /**
     * 验证服务签名
     *
     * <p>当签名头不存在时（兼容旧版 Gateway），仅记录警告并放行。
     * 生产环境应强制要求签名。
     */
    private boolean validateSignature(String serviceRole, HttpServletRequest request) {
        String signature = request.getHeader(SERVICE_SIGNATURE_HEADER);
        String timestampStr = request.getHeader(SERVICE_TIMESTAMP_HEADER);

        // 兼容模式：无签名头时放行（后续可强制要求）
        if (signature == null || timestampStr == null) {
            log.debug("No service signature provided, allowing without verification (compatibility mode)");
            return true;
        }

        try {
            long timestamp = Long.parseLong(timestampStr);
            long now = System.currentTimeMillis() / 1000;
            if (Math.abs(now - timestamp) > MAX_TIMESTAMP_AGE_SECONDS) {
                log.warn("Service signature timestamp expired: age={}s", Math.abs(now - timestamp));
                return false;
            }

            String expectedSignature = computeHmac(serviceRole, timestamp);
            if (expectedSignature == null) {
                return false;
            }

            // 常量时间比较防时序攻击
            byte[] expected = expectedSignature.getBytes(StandardCharsets.UTF_8);
            byte[] provided = signature.getBytes(StandardCharsets.UTF_8);
            return expected.length == provided.length && MessageDigest.isEqual(expected, provided);

        } catch (NumberFormatException e) {
            log.warn("Invalid timestamp format in service signature");
            return false;
        }
    }

    private String computeHmac(String serviceRole, long timestamp) {
        try {
            Mac mac = Mac.getInstance(HMAC_ALGORITHM);
            mac.init(new SecretKeySpec(sharedSecret.getBytes(StandardCharsets.UTF_8), HMAC_ALGORITHM));
            String payload = serviceRole + ":" + timestamp;
            byte[] hmacBytes = mac.doFinal(payload.getBytes(StandardCharsets.UTF_8));
            return bytesToHex(hmacBytes);
        } catch (Exception e) {
            log.error("HMAC computation error", e);
            return null;
        }
    }

    private static String bytesToHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format("%02x", b));
        }
        return sb.toString();
    }
}
