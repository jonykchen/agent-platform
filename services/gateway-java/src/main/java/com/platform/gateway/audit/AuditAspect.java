package com.platform.gateway.audit;

import com.platform.gateway.entity.AuditEvent;
import com.platform.gateway.service.AuditService;
import com.platform.gateway.service.TenantContextService;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Map;

/**
 * 审计切面
 * 自动拦截带有 @AuditLog 注解的方法，记录审计事件
 *
 * 功能：
 * - 自动提取租户 ID、用户 ID
 * - 自动提取请求 IP、User-Agent
 * - 支持 SpEL 表达式计算资源 ID
 * - 异步写入，不阻塞主流程
 */
@Slf4j
@Aspect
@Component
@RequiredArgsConstructor
public class AuditAspect {

    private final AuditService auditService;
    private final TenantContextService tenantContextService;

    /**
     * 拦截所有带有 @AuditLog 注解的方法
     */
    @Around("@annotation(com.platform.gateway.audit.AuditLog)")
    public Object audit(ProceedingJoinPoint joinPoint) throws Throwable {
        MethodSignature signature = (MethodSignature) joinPoint.getSignature();
        Method method = signature.getMethod();
        AuditLog auditLog = method.getAnnotation(AuditLog.class);

        // 记录开始时间
        long startTime = System.currentTimeMillis();

        // 构建审计事件
        AuditEvent.AuditEventBuilder eventBuilder = AuditEvent.builder();

        // 提取上下文信息
        extractContext(eventBuilder);

        // 设置注解属性
        eventBuilder
            .eventType(auditLog.type())
            .eventCategory(auditLog.category())
            .severity(auditLog.severity())
            .action(auditLog.action().isEmpty() ? auditLog.type() : auditLog.action())
            .resourceType(auditLog.resourceType());

        // 记录方法参数
        if (auditLog.logArguments()) {
            Map<String, Object> details = new HashMap<>();
            String[] paramNames = signature.getParameterNames();
            Object[] args = joinPoint.getArgs();
            for (int i = 0; i < paramNames.length && i < args.length; i++) {
                details.put(paramNames[i], maskSensitive(paramNames[i], args[i]));
            }
            eventBuilder.details(details);
        }

        try {
            // 执行原方法
            Object result = joinPoint.proceed();

            // 记录返回值
            if (auditLog.logResult() && result != null) {
                Map<String, Object> afterState = new HashMap<>();
                afterState.put("result", maskSensitive("result", result));
                eventBuilder.afterState(afterState);
            }

            // 记录执行时间
            long duration = System.currentTimeMillis() - startTime;
            Map<String, Object> details = eventBuilder.build().getDetails();
            if (details == null) {
                details = new HashMap<>();
            }
            details.put("duration_ms", duration);
            details.put("status", "success");
            eventBuilder.details(details);

            // 异步记录审计事件
            auditService.recordEvent(eventBuilder.build());

            return result;

        } catch (Throwable ex) {
            // 记录异常信息
            Map<String, Object> details = eventBuilder.build().getDetails();
            if (details == null) {
                details = new HashMap<>();
            }
            details.put("status", "failed");
            details.put("error", ex.getMessage());
            details.put("duration_ms", System.currentTimeMillis() - startTime);
            eventBuilder.details(details);

            // 提升严重程度
            if ("info".equals(auditLog.severity())) {
                eventBuilder.severity("warn");
            }

            auditService.recordEvent(eventBuilder.build());

            throw ex;
        }
    }

    /**
     * 提取请求上下文信息
     */
    private void extractContext(AuditEvent.AuditEventBuilder builder) {
        // 租户 ID
        String tenantId = tenantContextService.getCurrentTenantId();
        if (tenantId != null) {
            builder.tenantId(tenantId);
        } else {
            builder.tenantId("system");
        }

        // 用户 ID
        String userId = getCurrentUserId();
        builder.userId(userId != null ? userId : "anonymous");

        // Request ID 和 Trace ID
        builder.requestId(tenantContextService.getCurrentRequestId());
        builder.traceId(tenantContextService.getCurrentRequestId()); // Use requestId as traceId

        // HTTP 请求信息
        ServletRequestAttributes attrs = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attrs != null) {
            HttpServletRequest request = attrs.getRequest();
            builder.ipAddress(getClientIp(request));
            builder.userAgent(request.getHeader("User-Agent"));
            builder.sourceService("gateway-java");
        }
    }

    /**
     * 获取当前用户 ID
     */
    private String getCurrentUserId() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (auth != null && auth.isAuthenticated() && !"anonymousUser".equals(auth.getPrincipal())) {
            return auth.getName();
        }
        return null;
    }

    /**
     * 获取客户端真实 IP
     */
    private String getClientIp(HttpServletRequest request) {
        String ip = request.getHeader("X-Forwarded-For");
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getHeader("X-Real-IP");
        }
        if (ip == null || ip.isEmpty() || "unknown".equalsIgnoreCase(ip)) {
            ip = request.getRemoteAddr();
        }
        // 多个代理时取第一个
        if (ip != null && ip.contains(",")) {
            ip = ip.split(",")[0].trim();
        }
        return ip;
    }

    /**
     * 敏感数据脱敏
     */
    private Object maskSensitive(String fieldName, Object value) {
        if (value == null) {
            return null;
        }

        String lowerName = fieldName.toLowerCase();
        if (lowerName.contains("password") || lowerName.contains("secret") || lowerName.contains("token")) {
            return "******";
        }

        if (value instanceof String str) {
            // 手机号脱敏
            if (str.matches("1[3-9]\\d{9}")) {
                return str.substring(0, 3) + "****" + str.substring(7);
            }
            // 邮箱脱敏
            if (str.contains("@") && str.length() > 5) {
                int at = str.indexOf("@");
                return str.substring(0, Math.min(2, at)) + "***" + str.substring(at);
            }
            // 截断过长内容
            if (str.length() > 500) {
                return str.substring(0, 500) + "... (truncated)";
            }
        }

        return value;
    }
}