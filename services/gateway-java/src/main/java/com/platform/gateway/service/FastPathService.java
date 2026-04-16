package com.platform.gateway.service;

import com.platform.gateway.dto.request.ChatRequest;
import com.platform.gateway.dto.response.ChatResponse;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

/**
 * 快速路径服务 (P-01)
 * 简单问答直接透传，不经过完整 Agent 编排
 *
 * 【核心概念】短路径优化
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * Agent 编排（LangGraph 状态机）是重量级操作：
 * - 需调用 LLM 推理（延迟 1-3 秒）
 * - 需管理状态和 Checkpoint
 * - 对于简单问答（如"你好"），这是资源浪费
 *
 * 快速路径直接返回预定义响应，延迟 < 50ms。
 *
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          请求处理流程                                       │
 * │                                                                             │
 * │   用户请求                                                                  │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌─────────────┐                                                          │
 * │   │ 快速路径判断 │                                                          │
 * │   └─────────────┘                                                          │
 * │       │                                                                     │
 * │       ├──[是]──► 直接返回预定义响应（延迟 < 50ms）                          │
 * │       │                                                                     │
 * │       └──[否]──► 调用 Orchestrator（延迟 1-5s）                            │
 * │                   │                                                         │
 * │                   ▼                                                         │
 * │              LangGraph Agent 编排                                           │
 * │                   │                                                         │
 * │                   ▼                                                         │
 * │              返回响应                                                       │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *
 * 【技术选型】快速路径判断方案
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 关键词匹配 (选择)  │ • 简单高效                  │ • 需维护关键词列表          │
 * │                    │ • 零依赖                    │ • 无法处理复杂语义          │
 * │                    │ • 延迟最低                  │                              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 正则表达式         │ • 灵活匹配                  │ • 复杂模式难维护            │
 * │                    │ • 支持模糊匹配              │ • 性能不如关键词集合        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 机器学习分类       │ • 准确率高                  │ • 模型部署复杂              │
 * │ (如意图分类模型)   │ • 可处理语义变体            │ • 推理延迟增加              │
 * │                    │                             │ • 需训练数据                │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ LLM 意图分类       │ • 最灵活                    │ • 延迟反而增加（需调用LLM） │
 * │                    │                             │ • 成本高                    │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【选择关键词匹配的原因】
 * 1. 快速路径目标是"快"，任何额外处理都违背初衷
 * 2. 简单问候语（"你好"、"谢谢"）语义固定，无需复杂分类
 * 3. 误判成本低：即使走完整编排，也只是多几秒延迟
 *
 * 【判断规则】
 * 1. 匹配快速路径关键词（你好、谢谢、帮助等）
 * 2. 不匹配跳过关键词（查询、执行、删除等）
 * 3. 消息长度 < 100 字符
 * 4. 不包含换行符（多行通常是复杂请求）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FastPathService {

    @Value("${gateway.fast-path.enabled:true}")
    private boolean fastPathEnabled;

    @Value("${gateway.fast-path.max-length:100}")
    private int fastPathMaxLength;

    // 快速路径关键词（简单问答模式）
    private static final Set<String> FAST_PATH_PATTERNS = Set.of(
            "你好", "您好", "hi", "hello", "hey",
            "谢谢", "感谢", "thanks", "thank you",
            "再见", "拜拜", "bye", "goodbye",
            "帮助", "help", "?"
    );

    // 跳过快速路径的关键词（需要完整编排）
    private static final Set<String> SKIP_PATTERNS = Set.of(
            "查询", "搜索", "查找", "帮我", "请帮我",
            "执行", "操作", "修改", "删除", "创建",
            "query", "search", "find", "help me", "execute"
    );

    /**
     * 判断是否走快速路径
     */
    public boolean isFastPath(String message) {
        if (!fastPathEnabled || message == null) {
            return false;
        }

        String trimmed = message.trim().toLowerCase();

        // 消息过长，不走快速路径
        if (trimmed.length() > fastPathMaxLength) {
            return false;
        }

        // 包含需要完整编排的关键词
        for (String skip : SKIP_PATTERNS) {
            if (trimmed.contains(skip.toLowerCase())) {
                return false;
            }
        }

        // 匹配快速路径模式
        for (String pattern : FAST_PATH_PATTERNS) {
            if (trimmed.contains(pattern.toLowerCase()) || trimmed.equals(pattern.toLowerCase())) {
                return true;
            }
        }

        // 短消息（< 20 字符）且不含特殊字符，可能是简单问答
        if (trimmed.length() < 20 && !trimmed.contains("\n")) {
            return true;
        }

        return false;
    }

    /**
     * 处理快速路径请求
     */
    public ChatResponse handleFastPath(ChatRequest request) {
        long startTime = System.currentTimeMillis();

        String message = request.getMessage().trim();
        String response = generateSimpleResponse(message);

        return ChatResponse.builder()
                .requestId(RequestIdGenerator.getCurrent())
                .response(response)
                .modelUsed("fast-path")
                .promptTokens(estimateTokens(message))
                .completionTokens(estimateTokens(response))
                .totalTokens(estimateTokens(message) + estimateTokens(response))
                .costUsd(0.0)
                .createdAt(System.currentTimeMillis())
                .latencyMs((int) (System.currentTimeMillis() - startTime))
                .finishReason("stop")
                .build();
    }

    private String generateSimpleResponse(String message) {
        String lower = message.toLowerCase();

        if (lower.contains("你好") || lower.contains("您好") || lower.contains("hi") || lower.contains("hello")) {
            return "您好！我是智能助手，有什么可以帮助您的吗？";
        }

        if (lower.contains("谢谢") || lower.contains("感谢") || lower.contains("thanks")) {
            return "不客气，很高兴能帮助到您！";
        }

        if (lower.contains("再见") || lower.contains("拜拜") || lower.contains("bye")) {
            return "再见，祝您有愉快的一天！";
        }

        if (lower.contains("帮助") || lower.contains("help") || lower.contains("?")) {
            return "我可以帮助您：\n" +
                    "1. 回答问题和提供信息\n" +
                    "2. 查询业务数据\n" +
                    "3. 执行业务操作\n" +
                    "请告诉我您需要什么帮助？";
        }

        // 默认回复
        return "我收到了您的消息。请问有什么具体需要帮助的吗？";
    }

    private int estimateTokens(String text) {
        if (text == null) return 0;
        // 简单估算：中文约 1.5 字符/token，英文约 4 字符/token
        return (int) (text.length() * 0.5);
    }
}