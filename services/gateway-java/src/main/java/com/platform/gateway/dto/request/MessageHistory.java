package com.platform.gateway.dto.request;

import lombok.Data;

/**
 * 对话历史消息 DTO
 *
 * <p>用于传递历史对话记录，支持多轮对话上下文。
 *
 * <p>【使用场景】
 * <ul>
 *   <li>ChatRequest.history 字段</li>
 * </ul>
 *
 * <p>【消息顺序】按时间正序排列，最早的在前
 *
 * @see ChatRequest
 * @see com.platform.gateway.controller.ChatController
 */
@Data
public class MessageHistory {

    /**
     * 消息角色
     *
     * <p>标识消息的发送者角色。
     *
     * <p>【可选值】
     * <ul>
     *   <li>user - 用户消息</li>
     *   <li>assistant - AI 助手消息</li>
     *   <li>system - 系统提示消息</li>
     * </ul>
     */
    private String role;

    /**
     * 消息内容
     *
     * <p>消息的文本内容。
     */
    private String content;
}