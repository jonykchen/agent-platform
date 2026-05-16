package com.platform.gateway.dto.response;

import lombok.Data;

/**
 * 工具调用信息 DTO
 *
 * <p>记录对话过程中发生的工具调用详情。
 *
 * <p>【使用场景】
 * <ul>
 *   <li>ChatResponse.toolCalls 字段</li>
 *   <li>审计日志中的工具调用记录</li>
 * </ul>
 *
 * <p>【调用流程】
 * <ol>
 *   <li>模型决定调用工具，返回 callId 和工具名</li>
 *   <li>系统执行工具，返回执行结果</li>
 *   <li>结果反馈给模型继续生成回复</li>
 * </ol>
 *
 * @see ChatResponse
 * @see com.platform.gateway.controller.ChatController
 */
@Data
public class ToolCallInfo {

    /**
     * 调用ID
     *
     * <p>工具调用的唯一标识，用于关联调用请求和结果。
     *
     * <p>【格式】call_xxx，如 call_abc123
     */
    private String callId;

    /**
     * 工具名称
     *
     * <p>被调用的工具名称，采用 verb_noun 命名风格。
     *
     * <p>【示例】query_order、send_notification
     */
    private String toolName;

    /**
     * 调用参数（JSON 格式）
     *
     * <p>传递给工具的参数，JSON 字符串格式。
     *
     * <p>【格式】JSON 字符串，如 "{\"orderId\":\"12345\"}"
     */
    private String argumentsJson;
}