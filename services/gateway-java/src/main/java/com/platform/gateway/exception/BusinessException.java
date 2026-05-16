package com.platform.gateway.exception;

import lombok.Getter;

/**
 * 业务异常基类 - 统一异常处理的核心载体
 *
 * <h2>异常设计原则</h2>
 *
 * <h3>1. 语义化异常</h3>
 * <p>
 * BusinessException 携带完整的错误上下文，包括错误码、技术信息和用户友好信息，
 * 使异常不仅仅是一个信号，更是一个自描述的错误载体。
 * </p>
 *
 * <h3>2. 错误码与异常分离</h3>
 * <p>
 * 错误码定义集中在 {@link ErrorCode} 枚举中，BusinessException 持有 ErrorCode 引用。
 * 这种设计实现了：
 * </p>
 * <ul>
 *   <li><b>统一管理</b>：所有错误码在一处定义，便于维护和审计</li>
 *   <li><b>类型安全</b>：编译期检查错误码有效性</li>
 *   <li><b>避免魔法值</b>：杜绝硬编码错误码字符串</li>
 * </ul>
 *
 * <h3>3. 双信息设计</h3>
 * <p>
 * 每个异常包含两种信息：
 * </p>
 * <ul>
 *   <li><b>message</b>：技术信息，记录详细错误原因，用于日志和调试</li>
 *   <li><b>userMessage</b>：用户友好信息，面向终端用户，避免暴露技术细节</li>
 * </ul>
 *
 * <h2>错误码分类体系</h2>
 * <table border="1">
 *   <tr><th>范围</th><th>类别</th><th>示例</th><th>说明</th></tr>
 *   <tr>
 *     <td><b>10xxx</b></td>
 *     <td>通用错误</td>
 *     <td>ERR_INVALID_REQUEST, ERR_UNAUTHORIZED</td>
 *     <td>请求格式、认证授权等基础错误</td>
 *   </tr>
 *   <tr>
 *     <td><b>20xxx</b></td>
 *     <td>Agent 编排错误</td>
 *     <td>ERR_AGENT_MAX_STEPS_EXCEEDED</td>
 *     <td>Agent 执行过程中的业务错误</td>
 *   </tr>
 *   <tr>
 *     <td><b>21xxx</b></td>
 *     <td>会话错误</td>
 *     <td>ERR_SESSION_NOT_FOUND</td>
 *     <td>会话生命周期相关错误</td>
 *   </tr>
 *   <tr>
 *     <td><b>30xxx</b></td>
 *     <td>模型网关错误</td>
 *     <td>ERR_MODEL_ALL_PROVIDERS_DOWN</td>
 *     <td>LLM Provider 调用相关错误</td>
 *   </tr>
 *   <tr>
 *     <td><b>40xxx</b></td>
 *     <td>工具总线错误</td>
 *     <td>ERR_TOOL_VALIDATION_FAILED</td>
 *     <td>工具调用、校验、执行相关错误</td>
 *   </tr>
 *   <tr>
 *     <td><b>50xxx</b></td>
 *     <td>用户错误</td>
 *     <td>ERR_USER_NOT_FOUND</td>
 *     <td>用户账户相关错误</td>
 *   </tr>
 *   <tr>
 *     <td><b>60xxx</b></td>
 *     <td>审批错误</td>
 *     <td>ERR_APPROVAL_EXPIRED</td>
 *     <td>人工审批流程相关错误</td>
 *   </tr>
 *   <tr>
 *     <td><b>70xxx</b></td>
 *     <td>租户配额错误</td>
 *     <td>ERR_TENANT_QUOTA_EXCEEDED</td>
 *     <td>多租户资源限制错误</td>
 *   </tr>
 * </table>
 *
 * <h2>与 ErrorCode 的关系</h2>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                      ErrorCode (枚举)                           │
 * │  ┌─────────────────────────────────────────────────────────┐   │
 * │  │ ERR_TOOL_VALIDATION_FAILED                              │   │
 * │  │   ├── code: "ERR_TOOL_VALIDATION_FAILED"                │   │
 * │  │   ├── message: "Tool validation failed"                  │   │
 * │  │   ├── userMessage: "参数校验失败"                          │   │
 * │  │   └── httpStatus: 400                                    │   │
 * │  └─────────────────────────────────────────────────────────┘   │
 * └─────────────────────────────────────────────────────────────────┘
 *                            │
 *                            │ 引用
 *                            ▼
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                     BusinessException                            │
 * │  ┌─────────────────────────────────────────────────────────┐   │
 * │  │ errorCode: ErrorCode (引用)                              │   │
 * │  │ message: "JSON Schema 校验失败: 缺少必填字段 userId"      │   │
 * │  │ userMessage: "参数校验失败" (继承自 ErrorCode)            │   │
 * │  │ details: {"field": "userId", "reason": "required"}      │   │
 * │  └─────────────────────────────────────────────────────────┘   │
 * └─────────────────────────────────────────────────────────────────┘
 *                            │
 *                            │ 抛出
 *                            ▼
 * ┌─────────────────────────────────────────────────────────────────┐
 * │                   GlobalExceptionHandler                        │
 * │  构建 ErrorResponse，记录审计日志，返回 HTTP 响应              │
 * └─────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>使用示例</h2>
 * <pre>{@code
 * // 场景1：简单异常
 * throw BusinessException.of(ErrorCode.ERR_NOT_FOUND);
 *
 * // 场景2：带详细错误信息
 * throw BusinessException.of(ErrorCode.ERR_TOOL_VALIDATION_FAILED,
 *     "JSON Schema 校验失败: 缺少必填字段 userId");
 *
 * // 场景3：带详细上下文
 * throw BusinessException.of(
 *     ErrorCode.ERR_TOOL_VALIDATION_FAILED,
 *     "JSON Schema 校验失败",
 *     Map.of("field", "userId", "reason", "required", "schema", schema)
 * );
 *
 * // 场景4：try-catch 中包装底层异常
 * try {
 *     callExternalService();
 * } catch (ExternalServiceException e) {
 *     throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE,
 *         "External service unavailable: " + e.getMessage());
 * }
 * }</pre>
 *
 * <h2>最佳实践</h2>
 * <ul>
 *   <li><b>优先使用静态工厂方法</b>：of() 方法比构造器更简洁</li>
 *   <li><b>message 包含调试信息</b>：如参数名、字段名、具体值</li>
 *   <li><b>避免敏感信息泄露</b>：敏感数据只在 details 中传递，不放入 message</li>
 *   <li><b>details 使用 Map 或 POJO</b>：会被序列化为 JSON 返回给客户端</li>
 * </ul>
 *
 * @see ErrorCode 错误码枚举定义
 * @see GlobalExceptionHandler 全局异常处理器
 * @see ErrorResponse 统一错误响应格式
 */
@Getter
public class BusinessException extends RuntimeException {

    /**
     * 错误码枚举引用
     * <p>包含错误码、默认消息、用户消息和 HTTP 状态码</p>
     */
    private final ErrorCode errorCode;

    /**
     * 用户友好消息
     * <p>面向终端用户的错误描述，不应包含技术细节</p>
     * <p>默认继承自 ErrorCode.userMessage，可在构造时覆盖</p>
     */
    private final String userMessage;

    /**
     * 详细错误上下文
     * <p>可包含任意结构化数据，如：校验失败的字段名、期望值等</p>
     * <p>会被序列化为 JSON 返回给客户端，注意不要包含敏感信息</p>
     */
    private final Object details;

    /**
     * 创建业务异常（使用 ErrorCode 默认消息）
     *
     * @param errorCode 错误码枚举
     */
    public BusinessException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
        this.userMessage = errorCode.getUserMessage();
        this.details = null;
    }

    /**
     * 创建业务异常（自定义技术消息）
     *
     * @param errorCode 错误码枚举
     * @param message   详细技术消息，用于日志和调试
     */
    public BusinessException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
        this.userMessage = errorCode.getUserMessage();
        this.details = null;
    }

    /**
     * 创建业务异常（自定义技术消息和详细上下文）
     *
     * @param errorCode 错误码枚举
     * @param message   详细技术消息，用于日志和调试
     * @param details   详细错误上下文，将被序列化为 JSON
     */
    public BusinessException(ErrorCode errorCode, String message, Object details) {
        super(message);
        this.errorCode = errorCode;
        this.userMessage = errorCode.getUserMessage();
        this.details = details;
    }

    /**
     * 静态工厂方法：创建简单业务异常
     *
     * @param errorCode 错误码枚举
     * @return 业务异常实例
     */
    public static BusinessException of(ErrorCode errorCode) {
        return new BusinessException(errorCode);
    }

    /**
     * 静态工厂方法：创建带消息的业务异常
     *
     * @param errorCode 错误码枚举
     * @param message   详细技术消息
     * @return 业务异常实例
     */
    public static BusinessException of(ErrorCode errorCode, String message) {
        return new BusinessException(errorCode, message);
    }

    /**
     * 静态工厂方法：创建带消息和上下文的业务异常
     *
     * @param errorCode 错误码枚举
     * @param message   详细技术消息
     * @param details   详细错误上下文
     * @return 业务异常实例
     */
    public static BusinessException of(ErrorCode errorCode, String message, Object details) {
        return new BusinessException(errorCode, message, details);
    }
}