package com.platform.gateway.audit;

import java.lang.annotation.*;

/**
 * 审计注解
 * 标注在 Controller 方法上，自动记录审计事件
 *
 * 使用示例：
 * <pre>
 * {@literal @}AuditLog(type = "user.login", category = "security", severity = "info")
 * public ResponseEntity<?> login(LoginRequest request) { ... }
 * </pre>
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface AuditLog {

    /**
     * 事件类型
     * 格式：module.action，如 user.login, tool.executed
     */
    String type();

    /**
     * 事件类别
     * lifecycle / security / business / system
     */
    String category() default "business";

    /**
     * 严重程度
     * info / warn / error / critical
     */
    String severity() default "info";

    /**
     * 操作描述（支持 SpEL 表达式）
     */
    String action() default "";

    /**
     * 资源类型
     */
    String resourceType() default "";

    /**
     * 资源 ID 的 SpEL 表达式
     */
    String resourceIdExpression() default "";

    /**
     * 是否记录方法参数
     */
    boolean logArguments() default false;

    /**
     * 是否记录返回值
     */
    boolean logResult() default false;
}