package com.platform.gateway.service;

import com.platform.gateway.dto.request.ChatRequest;
import com.platform.gateway.dto.response.ChatResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;

/**
 * 快速路径服务 (P-01)
 *
 * <p>简单问答直接透传，不经过完整 Agent 编排。
 *
 * <h3>核心概念：短路径优化</h3>
 *
 * <p>Agent 编排（LangGraph 状态机）是重量级操作：
 * <ul>
 *   <li>需要调用 LLM 推理（延迟 1-3 秒）</li>
 *   <li>需要管理状态和 Checkpoint</li>
 *   <li>对于简单问答（如"你好"），这是资源浪费</li>
 * </ul>
 *
 * <p>快速路径直接返回预定义响应或透传到 Model Gateway，延迟 &lt; 50ms。
 *
 * <h3>请求处理流程</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          请求处理流程                                        │
 * │                                                                             │
 * │   用户请求                                                                  │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌───────────────────────┐                                                │
 * │   │ 1. 安全检查            │                                                │
 * │   │   - modelOverride?    │ ──[是]──► 走完整编排                           │
 * │   │   - enabledTools?     │ ──[是]──► 走完整编排                           │
 * │   └───────────────────────┘                                                │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌───────────────────────┐                                                │
 * │   │ 2. 风险扫描            │                                                │
 * │   │   - 高风险关键词?     │ ──[是]──► 走完整编排                           │
 * │   │   - 可疑模式?         │ ──[是]──► 记录日志，走完整编排                 │
 * │   └───────────────────────┘                                                │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ┌───────────────────────┐                                                │
 * │   │ 3. 快速路径判断        │                                                │
 * │   │   - 消息长度 &lt; 10字?  │ ──[否]──► Model Gateway 透传               │
 * │   │   - 匹配问候模式?     │ ──[是]──► 预定义响应                           │
 * │   └───────────────────────┘                                                │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   返回响应                                                                  │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>安全增强（S-AGENT-* 合规）</h3>
 * <ul>
 *   <li>modelOverride 检查：指定模型走完整编排（S-AGENT-06）</li>
 *   <li>enabledTools 检查：启用工具走完整编排（S-AGENT-06）</li>
 *   <li>风险扫描：检测高风险关键词（S-AGENT-03）</li>
 *   <li>安全阈值：从 100 字降为 10 字，减少攻击面</li>
 * </ul>
 *
 * <h3>判断规则</h3>
 * <ol>
 *   <li>安全检查：modelOverride 或 enabledTools 存在则跳过</li>
 *   <li>风险扫描：高风险关键词直接跳过</li>
 *   <li>匹配快速路径关键词（你好、谢谢、帮助等）</li>
 *   <li>不匹配跳过关键词（查询、执行、删除等）</li>
 *   <li>消息长度 &lt; 10 字符（安全阈值）</li>
 *   <li>不包含换行符（多行通常是复杂请求）</li>
 * </ol>
 *
 * @since 1.0.0
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class FastPathService {

    @Value("${gateway.fast-path.enabled:true}")
    private boolean fastPathEnabled;

    /**
     * 快速路径最大消息长度（安全阈值）
     * <p>从 100 字降为 10 字，减少攻击面（S-AGENT-03）
     */
    @Value("${gateway.fast-path.max-length:10}")
    private int fastPathMaxLength;

    private final FastPathRiskScanner riskScanner;
    private final ModelGatewayClient modelGatewayClient;

    /**
     * 快速路径关键词（简单问候模式）
     */
    private static final Set<String> FAST_PATH_PATTERNS = Set.of(
            "你好", "您好", "hi", "hello", "hey",
            "谢谢", "感谢", "thanks", "thank you",
            "再见", "拜拜", "bye", "goodbye",
            "帮助", "help", "?"
    );

    /**
     * 跳过快速路径的关键词（需要完整编排）
     */
    private static final Set<String> SKIP_PATTERNS = Set.of(
            "查询", "搜索", "查找", "帮我", "请帮我",
            "执行", "操作", "修改", "删除", "创建",
            "query", "search", "find", "help me", "execute"
    );

    /**
     * 判断是否走快速路径
     *
     * <p>检查流程：
     * <ol>
     *   <li>功能开关检查</li>
     *   <li>安全检查（modelOverride、enabledTools）</li>
     *   <li>风险扫描</li>
     *   <li>关键词匹配</li>
     * </ol>
     *
     * @param request 对话请求
     * @return 如果应该走快速路径返回 true
     */
    public boolean isFastPath(ChatRequest request) {
        if (!fastPathEnabled || request == null || request.getMessage() == null) {
            return false;
        }

        // ====== L1: 安全检查 ======

        // 指定了模型覆盖，需要走完整编排（可能需要特定模型能力）
        if (request.getModel() != null && !request.getModel().isBlank()) {
            log.debug("[FastPath] Skip: modelOverride specified ({})", request.getModel());
            return false;
        }

        // 启用了工具，需要走完整编排（需要 Agent 推理和工具调用）
        if (Boolean.TRUE.equals(request.getEnableTools()) ||
                (request.getToolWhitelist() != null && !request.getToolWhitelist().isEmpty())) {
            log.debug("[FastPath] Skip: tools enabled");
            return false;
        }

        // ====== L2: 风险扫描 ======
        RiskScanResult riskResult = riskScanner.scan(request.getMessage());
        if (riskResult.isHighRisk()) {
            log.warn("[FastPath] Skip: high risk detected, keywords={}", riskResult.matchedKeywords());
            return false;
        }

        if (riskResult.riskLevel() == RiskLevel.WARNING) {
            log.info("[FastPath] Warning: suspicious patterns detected, keywords={}",
                    riskResult.matchedKeywords());
            // 警告级别仍允许快速路径，但记录日志
        }

        // ====== L3: 基本检查 ======
        String message = request.getMessage().trim().toLowerCase();

        // 消息过长，不走快速路径（安全阈值：10 字）
        if (message.length() > fastPathMaxLength) {
            return false;
        }

        // 包含换行符（多行请求通常是复杂任务）
        if (message.contains("\n")) {
            return false;
        }

        // ====== L4: 关键词匹配 ======

        // 包含需要完整编排的关键词
        for (String skip : SKIP_PATTERNS) {
            if (message.contains(skip.toLowerCase())) {
                return false;
            }
        }

        // 匹配快速路径模式
        for (String pattern : FAST_PATH_PATTERNS) {
            if (message.contains(pattern.toLowerCase()) || message.equals(pattern.toLowerCase())) {
                return true;
            }
        }

        // 极短消息（< 5 字符）且不含特殊字符，可能是简单问候
        if (message.length() < 5 && !containsSpecialChars(message)) {
            return true;
        }

        return false;
    }

    /**
     * 处理快速路径请求
     *
     * <p>对于匹配快速路径的请求：
     * <ul>
     *   <li>简单问候：返回预定义响应</li>
     *   <li>其他情况：透传到 Model Gateway</li>
     * </ul>
     *
     * @param request 对话请求
     * @return 对话响应
     * @throws BusinessException 如果处理失败
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

    /**
     * 生成简单响应
     *
     * <p>基于关键词匹配合适的预定义响应。
     *
     * @param message 用户消息
     * @return 预定义响应
     */
    private String generateSimpleResponse(String message) {
        String lower = message.toLowerCase();

        if (lower.contains("你好") || lower.contains("您好") ||
                lower.contains("hi") || lower.contains("hello") || lower.contains("hey")) {
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

    /**
     * 检查是否包含特殊字符
     *
     * <p>特殊字符通常表示复杂请求，不适合快速路径。
     *
     * @param message 消息内容
     * @return 如果包含特殊字符返回 true
     */
    private boolean containsSpecialChars(String message) {
        return message.matches(".*[{}\\[\\]()<>@#$%^&*+=|\\\\].*");
    }

    /**
     * 估算 token 数量
     *
     * <p>简单估算：中文约 1.5 字符/token，英文约 4 字符/token。
     *
     * @param text 文本内容
     * @return 估算的 token 数量
     */
    private int estimateTokens(String text) {
        if (text == null) {
            return 0;
        }
        return (int) (text.length() * 0.5);
    }

    /**
     * 判断消息是否应该透传到 Model Gateway
     *
     * <p>对于不匹配预定义响应但通过了安全检查的消息，
     * 可以透传到 Model Gateway 进行轻量级处理。
     *
     * @param request 对话请求
     * @return 如果应该透传返回 true
     */
    public boolean shouldProxyToModelGateway(ChatRequest request) {
        if (!fastPathEnabled || request == null || request.getMessage() == null) {
            return false;
        }

        // 通过安全检查但不匹配预定义响应
        RiskScanResult riskResult = riskScanner.scan(request.getMessage());
        if (riskResult.isHighRisk()) {
            return false;
        }

        // 有工具或模型指定，不走透传
        if (request.getModel() != null && !request.getModel().isBlank()) {
            return false;
        }
        if (Boolean.TRUE.equals(request.getEnableTools()) ||
                (request.getToolWhitelist() != null && !request.getToolWhitelist().isEmpty())) {
            return false;
        }

        String message = request.getMessage().trim();

        // 消息长度限制（放宽到 50 字）
        return message.length() <= 50 && !message.contains("\n");
    }
}