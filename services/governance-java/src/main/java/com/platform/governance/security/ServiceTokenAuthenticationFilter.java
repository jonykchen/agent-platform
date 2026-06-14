package com.platform.governance.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.web.filter.OncePerRequestFilter;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

/**
 * Service Token 认证过滤器
 *
 * <p>验证内部服务间调用时通过 {@code X-Service-Token} 头传递的 HMAC 签名 Token。
 * 与 ToolBus 的 {@code AuthServerInterceptor} 使用相同的认证机制。
 *
 * <h3>Token 格式</h3>
 * <pre>
 * X-Service-Token: {service_name}:{timestamp}:{hmac_sha256}
 * </pre>
 *
 * <h3>验证逻辑</h3>
 * <ol>
 *   <li>解析 Token 为 service_name + timestamp + hmac</li>
 *   <li>验证时间戳在 5 分钟内</li>
 *   <li>使用共享密钥重新计算 HMAC</li>
 *   <li>常量时间比较 HMAC（防时序攻击）</li>
 * </ol>
 */
@Slf4j
public class ServiceTokenAuthenticationFilter extends OncePerRequestFilter {

    private static final String HEADER_NAME = "X-Service-Token";
    private static final long TOKEN_MAX_AGE_SECONDS = 300; // 5 minutes
    private static final String HMAC_ALGORITHM = "HmacSHA256";

    private final String sharedSecret;

    public ServiceTokenAuthenticationFilter(String sharedSecret) {
        this.sharedSecret = sharedSecret;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {

        String token = request.getHeader(HEADER_NAME);

        if (token != null && SecurityContextHolder.getContext().getAuthentication() == null) {
            try {
                ServiceTokenInfo tokenInfo = parseAndValidate(token, request.getRequestURI());
                if (tokenInfo != null) {
                    var authorities = tokenInfo.serviceName().equals("gateway")
                        ? List.of(new SimpleGrantedAuthority("ROLE_SERVICE"))
                        : List.of(
                            new SimpleGrantedAuthority("ROLE_SERVICE"),
                            new SimpleGrantedAuthority("ROLE_APPROVER")
                        );

                    var authentication = new UsernamePasswordAuthenticationToken(
                        tokenInfo.serviceName(), null, authorities
                    );
                    authentication.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
                    SecurityContextHolder.getContext().setAuthentication(authentication);

                    log.debug("Service authenticated: {}", tokenInfo.serviceName());
                }
            } catch (Exception e) {
                log.warn("Service token validation failed: {}", e.getMessage());
            }
        }

        filterChain.doFilter(request, response);
    }

    private ServiceTokenInfo parseAndValidate(String token, String requestUri) {
        String[] parts = token.split(":", 3);
        if (parts.length != 3) {
            log.warn("Invalid token format");
            return null;
        }

        String serviceName = parts[0];
        long timestamp;
        try {
            timestamp = Long.parseLong(parts[1]);
        } catch (NumberFormatException e) {
            log.warn("Invalid timestamp in token");
            return null;
        }
        String providedHmac = parts[2];

        // 验证时间戳
        long now = System.currentTimeMillis() / 1000;
        if (Math.abs(now - timestamp) > TOKEN_MAX_AGE_SECONDS) {
            log.warn("Token expired or from future: age={}s", Math.abs(now - timestamp));
            return null;
        }

        // 验证 HMAC
        String expectedHmac = computeHmac(serviceName, timestamp, requestUri);
        if (expectedHmac == null) {
            log.warn("HMAC computation failed");
            return null;
        }

        // 常量时间比较防时序攻击
        byte[] expected = expectedHmac.getBytes(StandardCharsets.UTF_8);
        byte[] provided = providedHmac.getBytes(StandardCharsets.UTF_8);
        if (expected.length != provided.length || !MessageDigest.isEqual(expected, provided)) {
            log.warn("HMAC mismatch for service: {}", serviceName);
            return null;
        }

        return new ServiceTokenInfo(serviceName, timestamp);
    }

    private String computeHmac(String serviceName, long timestamp, String requestUri) {
        try {
            Mac mac = Mac.getInstance(HMAC_ALGORITHM);
            mac.init(new SecretKeySpec(sharedSecret.getBytes(StandardCharsets.UTF_8), HMAC_ALGORITHM));
            String payload = serviceName + ":" + timestamp + ":" + requestUri;
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

    /**
     * 解析后的 Token 信息
     */
    private record ServiceTokenInfo(String serviceName, long timestamp) {}
}
