package com.platform.gateway.dto.response;

import lombok.Builder;
import lombok.Data;

import java.util.List;

/**
 * 对话响应 DTO
 *
 * <p>对话请求的响应结果，包含 AI 生成的回复、Token 使用统计和工具调用信息。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/chat/completions - 对话补全接口</li>
 * </ul>
 *
 * <p>【响应字段说明】
 * <ul>
 *   <li>requestId: 全链路追踪标识</li>
 *   <li>response: AI 生成的回复文本</li>
 *   <li>modelUsed: 实际使用的模型名称</li>
 *   <li>promptTokens/completionTokens/totalTokens: Token 计数</li>
 *   <li>costUsd: 本次对话成本（美元）</li>
 *   <li>toolCalls: 工具调用记录</li>
 *   <li>finishReason: 完成原因（stop/tool_calls/error）</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.ChatController
 * @see com.platform.gateway.dto.request.ChatRequest
 * @see ToolCallInfo
 */
@Data
@Builder
public class ChatResponse {

    /**
     * 请求ID
     *
     * <p>全链路追踪标识，用于日志关联和问题排查。
     *
     * <p>【格式】req_xxx，如 req_abc123
     */
    private String requestId;

    /**
     * AI 回复内容
     *
     * <p>模型生成的对话回复文本。
     */
    private String response;

    /**
     * 使用的模型
     *
     * <p>实际处理请求的模型名称，可能与请求中指定的模型不同（如降级处理）。
     *
     * <p>【示例】qwen-plus、deepseek-chat
     */
    private String modelUsed;

    /**
     * 输入 Token 数
     *
     * <p>请求输入消耗的 Token 数量（包含系统提示和历史消息）。
     */
    private Integer promptTokens;

    /**
     * 输出 Token 数
     *
     * <p>模型生成消耗的 Token 数量。
     */
    private Integer completionTokens;

    /**
     * 总 Token 数
     *
     * <p>本次对话消耗的 Token 总数 = promptTokens + completionTokens。
     */
    private Integer totalTokens;

    /**
     * 成本（美元）
     *
     * <p>本次对话的成本，按模型定价计算。
     */
    private Double costUsd;

    /**
     * 工具调用记录
     *
     * <p>本次对话中调用的工具列表。若无工具调用则为 null。
     */
    private List<ToolCallInfo> toolCalls;

    /**
     * 创建时间戳
     *
     * <p>响应生成的时间（Unix 毫秒时间戳）。
     */
    private Long createdAt;

    /**
     * 响应延迟（毫秒）
     *
     * <p>从请求到达 Gateway 到响应返回的总延迟。
     */
    private Integer latencyMs;

    /**
     * 完成原因
     *
     * <p>模型停止生成的原因。
     *
     * <p>【可选值】
     * <ul>
     *   <li>stop - 正常完成</li>
     *   <li>tool_calls - 工具调用触发</li>
     *   <li>length - 达到最大 Token 限制</li>
     *   <li>content_filtered - 内容被过滤</li>
     *   <li>error - 发生错误</li>
     * </ul>
     */
    private String finishReason;

    /**
     * 错误信息
     *
     * <p>若发生错误，包含错误描述；正常响应时为 null。
     */
    private String error;
}