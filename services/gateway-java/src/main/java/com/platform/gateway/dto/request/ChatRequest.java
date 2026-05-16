package com.platform.gateway.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

import java.util.List;

/**
 * 对话请求 DTO
 *
 * <p>用于发起对话请求，支持多轮对话、工具调用和 RAG 增强等功能。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/chat/completions - 对话补全接口</li>
 * </ul>
 *
 * <p>【字段说明】
 * <ul>
 *   <li>message: 用户输入的消息内容（必填）</li>
 *   <li>history: 历史对话记录，用于多轮对话上下文</li>
 *   <li>model: 指定使用的模型，不填则使用默认模型</li>
 *   <li>temperature: 模型温度参数，控制输出随机性（0-2）</li>
 *   <li>maxTokens: 最大输出 Token 数</li>
 *   <li>stream: 是否启用流式输出</li>
 *   <li>enableRag: 是否启用 RAG 知识库增强</li>
 *   <li>enableTools: 是否启用工具调用</li>
 *   <li>toolWhitelist: 工具白名单，限制可调用的工具</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.ChatController
 * @see MessageHistory
 * @see com.platform.gateway.dto.response.ChatResponse
 */
@Data
public class ChatRequest {

    /**
     * 用户消息内容
     *
     * <p>用户输入的对话文本，是发起对话的核心输入。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>必填项，不能为空</li>
     *   <li>最大长度由 MAX_USER_INPUT_TOKENS 限制（8000 tokens）</li>
     * </ul>
     */
    @NotBlank(message = "消息不能为空")
    private String message;

    /**
     * 历史对话记录
     *
     * <p>用于多轮对话场景，传递历史上下文信息。
     * 每条记录包含角色（user/assistant/system）和内容。
     *
     * <p>【来源】前端维护的会话历史
     */
    private List<MessageHistory> history;

    /**
     * 指定模型名称
     *
     * <p>指定要使用的 LLM 模型。若不填写，系统将使用租户配置的默认模型。
     *
     * <p>【可选值示例】
     * <ul>
     *   <li>qwen-plus - 通义千问增强版</li>
     *   <li>qwen-turbo - 通义千问极速版</li>
     *   <li>deepseek-chat - DeepSeek 对话模型</li>
     * </ul>
     */
    private String model;

    /**
     * 温度参数
     *
     * <p>控制模型输出的随机性。值越大输出越随机，值越小输出越确定。
     *
     * <p>【取值范围】0.0 ~ 2.0
     * <ul>
     *   <li>0.0 ~ 0.3: 高确定性，适合事实性回答</li>
     *   <li>0.5 ~ 0.8: 平衡模式，适合一般对话</li>
     *   <li>1.0 ~ 2.0: 高创造性，适合创意写作</li>
     * </ul>
     */
    private Double temperature;

    /**
     * 最大输出 Token 数
     *
     * <p>限制模型生成的最大 Token 数量，用于控制响应长度和成本。
     *
     * <p>【取值范围】1 ~ 模型上下文窗口上限
     */
    private Integer maxTokens;

    /**
     * 是否启用流式输出
     *
     * <p>启用后响应将以 SSE（Server-Sent Events）方式流式返回，
     * 适合需要实时显示生成内容的前端场景。
     *
     * <p>【默认值】false
     */
    private Boolean stream;

    /**
     * 是否启用 RAG 知识库增强
     *
     * <p>启用后系统会检索相关知识库内容，增强模型的回答质量和准确性。
     *
     * <p>【默认值】true（按租户配置）
     */
    private Boolean enableRag;

    /**
     * 是否启用工具调用
     *
     * <p>启用后模型可以调用预定义的工具执行任务，如查询订单、发送通知等。
     *
     * <p>【默认值】true（按租户配置）
     */
    private Boolean enableTools;

    /**
     * 工具白名单
     *
     * <p>限制本次对话可调用的工具列表。若不填写，则使用租户配置的全部可用工具。
     *
     * <p>【格式】工具名称列表，如 ["query_order", "send_notification"]
     */
    private List<String> toolWhitelist;
}