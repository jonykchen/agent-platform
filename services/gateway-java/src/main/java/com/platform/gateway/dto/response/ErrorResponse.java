package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

/**
 * 统一错误响应 DTO
 *
 * <p>API 请求失败时返回的统一错误格式，便于前端统一处理。
 *
 * <p>【响应字段说明】
 * <ul>
 *   <li>error: 错误码（如 ERR_INVALID_REQUEST）</li>
 *   <li>message: 技术人员可读的错误描述</li>
 *   <li>userMessage: 用户友好的错误提示</li>
 *   <li>requestId: 用于追踪的请求标识</li>
 *   <li>details: 附加的错误详情（可选）</li>
 * </ul>
 *
 * <p>【错误码体系】
 * <ul>
 *   <li>10xxx: 请求类错误（参数、权限、限流）</li>
 *   <li>20xxx: Agent 类错误（步数超限、上下文超长）</li>
 *   <li>30xxx: 模型类错误（Provider 不可用、内容过滤）</li>
 *   <li>40xxx: 工具类错误（校验失败、执行失败、需审批）</li>
 * </ul>
 *
 * @see com.platform.gateway.exception.BusinessException
 * @see com.platform.gateway.exception.ErrorCode
 */
@Data
@Builder
public class ErrorResponse {

    /**
     * 错误码
     *
     * <p>业务错误码，便于前端进行错误分类处理。
     *
     * <p>【格式】ERR_xxx，如 ERR_INVALID_REQUEST、ERR_UNAUTHORIZED
     */
    private String error;

    /**
     * 技术错误信息
     *
     * <p>供技术人员排查问题的详细错误描述。
     */
    private String message;

    /**
     * 用户友好提示
     *
     * <p>面向用户的错误提示信息，可直接展示给用户。
     */
    private String userMessage;

    /**
     * 请求ID
     *
     * <p>全链路追踪标识，用于日志关联和问题排查。
     *
     * <p>【格式】req_xxx
     */
    private String requestId;

    /**
     * 错误详情
     *
     * <p>附加的错误详情，如字段校验错误列表等。
     *
     * <p>【类型】可以是任意对象，如 List&lt;FieldError&gt; 或 Map
     */
    private Object details;
}