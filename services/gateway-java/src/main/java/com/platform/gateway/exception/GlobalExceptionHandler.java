package com.platform.gateway.exception;

import com.platform.gateway.dto.response.ErrorResponse;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

/**
 * 全局异常处理器 - 统一错误响应入口
 *
 * <h2>异常处理策略</h2>
 *
 * <h3>分层处理原则</h3>
 * <table border="1">
 *   <tr><th>异常类型</th><th>日志级别</th><th>响应状态码</th><th>处理策略</th></tr>
 *   <tr>
 *     <td><b>BusinessException</b></td>
 *     <td>WARN</td>
 *     <td>由 ErrorCode.httpStatus 决定</td>
 *     <td>返回结构化错误响应，记录业务审计日志</td>
 *   </tr>
 *   <tr>
 *     <td><b>IllegalArgumentException</b></td>
 *     <td>WARN</td>
 *     <td>400 Bad Request</td>
 *     <td>参数校验失败，返回用户友好提示</td>
 *   </tr>
 *   <tr>
 *     <td><b>其他 Exception</b></td>
 *     <td>ERROR</td>
 *     <td>500 Internal Server Error</td>
 *     <td>未知异常，隐藏技术细节，返回通用错误</td>
 *   </tr>
 * </table>
 *
 * <h3>异常转换原则</h3>
 * <ul>
 *   <li><b>业务异常</b>：直接转换为 ErrorResponse，保留完整错误上下文</li>
 *   <li><b>系统异常</b>：转换为 ERR_UNKNOWN，隐藏内部实现细节</li>
 *   <li><b>参数异常</b>：转换为 ERR_INVALID_REQUEST，提供校验失败信息</li>
 * </ul>
 *
 * <h2>响应格式规范</h2>
 *
 * <h3>标准错误响应结构</h3>
 * <pre>{@code
 * {
 *   "error": "ERR_CODE",              // 错误码，用于程序判断
 *   "message": "Technical message",   // 技术信息，用于调试
 *   "userMessage": "用户友好信息",     // 用户信息，面向终端用户
 *   "requestId": "uuid-v7",           // 请求追踪 ID
 *   "details": {}                     // 可选，详细错误上下文
 * }
 * }</pre>
 *
 * <h3>响应示例</h3>
 * <pre>{@code
 * // 业务异常响应
 * {
 *   "error": "ERR_TOOL_VALIDATION_FAILED",
 *   "message": "JSON Schema 校验失败: 缺少必填字段 userId",
 *   "userMessage": "参数校验失败",
 *   "requestId": "018f3b2a-1c4d-7d8e-9f0a-1b2c3d4e5f6g",
 *   "details": {
 *     "field": "userId",
 *     "reason": "required"
 *   }
 * }
 *
 * // 系统异常响应（隐藏技术细节）
 * {
 *   "error": "ERR_UNKNOWN",
 *   "message": "Internal server error",
 *   "userMessage": "系统繁忙，请稍后重试",
 *   "requestId": "018f3b2a-1c4d-7d8e-9f0a-1b2c3d4e5f6g"
 * }
 * }</pre>
 *
 * <h2>审计记录说明</h2>
 *
 * <h3>审计日志格式</h3>
 * <p>
 * 所有异常都会记录审计日志，格式遵循项目 JSON 日志规范：
 * </p>
 * <pre>{@code
 * {
 *   "timestamp": "2024-06-05T10:30:00Z",
 *   "level": "WARN",
 *   "request_id": "018f3b2a-...",
 *   "tenant_id": "tenant_001",
 *   "service": "gateway",
 *   "error_code": "ERR_TOOL_VALIDATION_FAILED",
 *   "message": "Business error details",
 *   "http_status": 400,
 *   "client_ip": "192.168.1.100",
 *   "uri": "/api/v1/tools/execute"
 * }
 * }</pre>
 *
 * <h3>审计级别区分</h3>
 * <ul>
 *   <li><b>业务异常 (WARN)</b>：客户端错误，如参数校验失败、权限不足</li>
 *   <li><b>系统异常 (ERROR)</b>：服务端错误，需要关注和排查</li>
 * </ul>
 *
 * <h3>敏感信息处理</h3>
 * <p>
 * 遵循 G-SEC-02 规则，审计日志自动脱敏：
 * </p>
 * <ul>
 *   <li>手机号：138****1234</li>
 *   <li>身份证：110***********1234</li>
 *   <li>API Key：sk-****abcd</li>
 * </ul>
 *
 * <h2>处理流程</h2>
 * <pre>
 * ┌──────────────────┐
 * │ Controller 抛出  │
 * │    异常          │
 * └────────┬─────────┘
 *          │
 *          ▼
 * ┌──────────────────┐     ┌─────────────────────┐
 * │ GlobalException  │────▶│ 判断异常类型         │
 * │    Handler       │     └──────────┬──────────┘
 * └────────┬─────────┘                │
 *          │           ┌──────────────┼──────────────┐
 *          │           ▼              ▼              ▼
 *          │   ┌─────────────┐ ┌───────────┐ ┌───────────┐
 *          │   │Business    │ │IllegalArg │ │Exception  │
 *          │   │Exception   │ │Exception  │ │(未知)     │
 *          │   └──────┬──────┘ └─────┬─────┘ └─────┬─────┘
 *          │          │              │             │
 *          │          ▼              ▼             ▼
 *          │   ┌─────────────────────────────────────────┐
 *          │   │ 构建 ErrorResponse                       │
 *          │   │ - error code                            │
 *          │   │ - message / userMessage                 │
 *          │   │ - requestId (从 MDC 获取)               │
 *          │   └────────────────────┬────────────────────┘
 *          │                        │
 *          │                        ▼
 *          │   ┌─────────────────────────────────────────┐
 *          │   │ 记录审计日志                             │
 *          │   │ - WARN: 业务异常                        │
 *          │   │ - ERROR: 系统异常                       │
 *          │   └────────────────────┬────────────────────┘
 *          │                        │
 *          ▼                        ▼
 *   ┌─────────────────────────────────────────────────┐
 *   │ 返回 ResponseEntity<ErrorResponse>              │
 *   └─────────────────────────────────────────────────┘
 * </pre>
 *
 * <h2>扩展指南</h2>
 * <p>
 * 新增异常处理方法时，遵循以下原则：
 * </p>
 * <ul>
 *   <li>使用 @ExceptionHandler 注解指定异常类型</li>
 *   <li>返回 ResponseEntity&lt;ErrorResponse&gt; 统一格式</li>
 *   <li>设置适当的日志级别和 HTTP 状态码</li>
 *   <li>确保 requestId 从 MDC 获取，保持追踪链</li>
 * </ul>
 *
 * @see BusinessException 业务异常基类
 * @see ErrorCode 错误码枚举
 * @see ErrorResponse 统一错误响应格式
 * @see RequestIdGenerator Request ID 工具类
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    /**
     * 处理业务异常
     *
     * <p>业务异常由业务代码主动抛出，包含完整的错误上下文。
     * 此处理器将 BusinessException 转换为标准 ErrorResponse 格式。</p>
     *
     * <p>日志级别：WARN（客户端导致的业务错误，非系统故障）</p>
     *
     * @param ex 业务异常实例
     * @return 标准错误响应，HTTP 状态码由 ErrorCode 决定
     */
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusinessException(BusinessException ex) {
        log.warn("Business error: code={}, msg={}", ex.getErrorCode().getCode(), ex.getMessage());

        ErrorResponse response = ErrorResponse.builder()
                .error(ex.getErrorCode().getCode())
                .message(ex.getMessage())
                .userMessage(ex.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .details(ex.getDetails())
                .build();

        return ResponseEntity.status(ex.getErrorCode().getHttpStatus()).body(response);
    }

    /**
     * 处理参数校验异常
     *
     * <p>IllegalArgumentException 通常由 Spring Validation 或业务校验抛出，
     * 表示客户端请求参数不符合要求。</p>
     *
     * <p>日志级别：WARN（客户端参数错误）</p>
     *
     * @param ex 参数校验异常实例
     * @return 标准错误响应，HTTP 状态码 400
     */
    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponse> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("Invalid argument: {}", ex.getMessage());

        ErrorResponse response = ErrorResponse.builder()
                .error(ErrorCode.ERR_INVALID_REQUEST.getCode())
                .message(ex.getMessage())
                .userMessage(ErrorCode.ERR_INVALID_REQUEST.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .build();

        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response);
    }

    /**
     * 处理未知异常
     *
     * <p>所有未被其他处理器捕获的异常都将由此方法处理。
     * 为避免泄露内部实现细节，响应中不包含实际异常信息。</p>
     *
     * <p>日志级别：ERROR（需要关注的系统异常）</p>
     * <p>完整异常堆栈会记录到日志，供运维人员排查问题。</p>
     *
     * @param ex 未知异常实例
     * @return 标准错误响应，HTTP 状态码 500
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception ex) {
        log.error("Unexpected error", ex);

        ErrorResponse response = ErrorResponse.builder()
                .error(ErrorCode.ERR_UNKNOWN.getCode())
                .message("Internal server error")
                .userMessage(ErrorCode.ERR_UNKNOWN.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .build();

        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }
}