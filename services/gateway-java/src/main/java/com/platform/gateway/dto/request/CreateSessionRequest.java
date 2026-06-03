package com.platform.gateway.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 创建会话请求 DTO
 *
 * <p>用于创建新的对话会话，指定会话类型和初始标题。
 *
 * <p>【对应 API】
 * <ul>
 *   <li>POST /api/v1/sessions - 创建会话接口</li>
 * </ul>
 *
 * <p>【会话类型说明】
 * <ul>
 *   <li>chat - 普通对话会话，适合问答交互</li>
 *   <li>task - 任务型会话，适合执行特定任务</li>
 *   <li>workflow - 工作流会话，适合复杂多步骤操作</li>
 * </ul>
 *
 * @see com.platform.gateway.controller.SessionController
 * @see com.platform.gateway.dto.response.SessionResponse
 */
@Data
public class CreateSessionRequest {

    /**
     * 会话类型
     *
     * <p>定义会话的交互模式，影响 Agent 的行为策略。
     *
     * <p>【可选值】
     * <ul>
     *   <li>chat - 普通对话会话</li>
     *   <li>task - 任务型会话</li>
     *   <li>workflow - 工作流会话</li>
     * </ul>
     *
     * <p>【验证规则】可选，默认为 chat
     */
    private String sessionType = "chat";

    /**
     * 会话标题
     *
     * <p>会话的显示名称，用于在会话列表中标识会话。
     * 若不填写，系统会根据首条消息自动生成。
     *
     * <p>【验证规则】
     * <ul>
     *   <li>选填项</li>
     *   <li>最大长度 256 字符</li>
     * </ul>
     */
    @Size(max = 256, message = "标题最长256个字符")
    private String title;
}