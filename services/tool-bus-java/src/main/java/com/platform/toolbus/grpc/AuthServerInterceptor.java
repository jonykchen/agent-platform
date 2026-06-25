package com.platform.toolbus.grpc;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.grpc.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Base64;
import java.util.Map;
import java.util.Set;

/**
 * gRPC 服务端认证拦截器
 *
 * 验证：
 * - Service Token 签名和有效期
 * - 调用方服务身份（白名单）
 */
@Slf4j
@Component
public class AuthServerInterceptor implements ServerInterceptor {

    private final Set<String> validServices;
    private final String tokenSecret;
    private final String issuer;
    private final Set<String> skipMethods;

    public AuthServerInterceptor(
            @Value("${grpc.auth.valid-services:orchestrator,gateway}") Set<String> validServices,
            @Value("${grpc.auth.secret:}") String tokenSecret,
            @Value("${grpc.auth.issuer:agent-platform}") String issuer
    ) {
        this.validServices = validServices;
        this.tokenSecret = tokenSecret;
        this.issuer = issuer;
        this.skipMethods = Set.of(
            "grpc.health.v1.Health/Check",
            "grpc.health.v1.Health/Watch"
        );
    }

    @Override
    public <ReqT, RespT> ServerCall.Listener<ReqT> interceptCall(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            ServerCallHandler<ReqT, RespT> next
    ) {
        String method = call.getMethodDescriptor().getFullMethodName();

        // 跳过健康检查
        if (skipMethods.contains(method)) {
            return next.startCall(call, headers);
        }

        // 提取 metadata
        Metadata.Key<String> authKey = Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);
        Metadata.Key<String> serviceKey = Metadata.Key.of("x-service-name", Metadata.ASCII_STRING_MARSHALLER);
        Metadata.Key<String> requestIdKey = Metadata.Key.of("x-request-id", Metadata.ASCII_STRING_MARSHALLER);

        String authHeader = headers.get(authKey);
        String serviceName = headers.get(serviceKey);
        String requestId = headers.get(requestIdKey);

        // 1. 验证 Token 存在
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            log.warn("Missing authorization header: method={}", method);
            return abort(call, headers, Status.UNAUTHENTICATED.withDescription("Missing authorization header"));
        }

        String token = authHeader.substring(7);

        // 2. 验证 Token
        try {
            validateToken(token);
        } catch (Exception e) {
            log.warn("Token validation failed: method={}, error={}", method, e.getMessage());
            return abort(call, headers, Status.UNAUTHENTICATED.withDescription("Invalid token: " + e.getMessage()));
        }

        // 3. 验证服务身份
        if (serviceName == null || !validServices.contains(serviceName)) {
            log.warn("Unauthorized service: method={}, service={}, validServices={}",
                method, serviceName, validServices);
            return abort(call, headers, Status.PERMISSION_DENIED.withDescription("Unauthorized service: " + serviceName));
        }

        log.debug("gRPC call authenticated: method={}, service={}, requestId={}", method, serviceName, requestId);

        return next.startCall(call, headers);
    }

    private <ReqT, RespT> ServerCall.Listener<ReqT> abort(
            ServerCall<ReqT, RespT> call,
            Metadata headers,
            Status status
    ) {
        call.close(status, headers);
        return new ServerCall.Listener<>() {};
    }

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 验证 Service Token
     */
    private void validateToken(String token) throws Exception {
        String[] parts = token.split("\\.");
        if (parts.length != 2) {
            throw new IllegalArgumentException("Invalid token format");
        }

        String payloadB64 = parts[0];
        String signatureB64 = parts[1];

        // 验证签名（使用恒定时间比较，防止时序攻击）
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(tokenSecret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
        byte[] expectedSignature = mac.doFinal(payloadB64.getBytes(StandardCharsets.UTF_8));

        byte[] actualSignature = Base64.getUrlDecoder().decode(signatureB64);

        if (!MessageDigest.isEqual(expectedSignature, actualSignature)) {
            throw new IllegalArgumentException("Invalid signature");
        }

        // 使用 ObjectMapper 解析 payload（替换手写 indexOf 解析，防止格式变体绕过）
        String payloadJson = new String(Base64.getUrlDecoder().decode(payloadB64), StandardCharsets.UTF_8);
        Map<String, Object> payload = objectMapper.readValue(payloadJson, Map.class);

        // 验证过期时间
        Object expObj = payload.get("exp");
        if (expObj == null) {
            throw new IllegalArgumentException("Token missing required 'exp' field");
        }
        long exp = ((Number) expObj).longValue();
        if (exp < System.currentTimeMillis() / 1000) {
            throw new IllegalArgumentException("Token expired");
        }

        // 验证签发者
        Object issObj = payload.get("iss");
        if (!issuer.equals(issObj)) {
            throw new IllegalArgumentException("Invalid issuer");
        }
    }
}
