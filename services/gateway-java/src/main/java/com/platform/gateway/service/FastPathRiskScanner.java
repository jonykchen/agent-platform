package com.platform.gateway.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArraySet;

/**
 * 快速路径风险扫描器
 *
 * <p>检测用户输入中的高风险关键词和可疑模式，防止恶意请求绕过安全检查。
 *
 * <h3>检测层级</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          风险检测层级                                        │
 * │                                                                             │
 * │   L1: 高风险关键词（必须拦截）                                               │
 * │   ├── 删除类: 删除、清空、移除、drop、delete、truncate...                    │
 * │   ├── 资金类: 转账、支付、扣款、transfer、payment...                         │
 * │   ├── 权限类: 授权、提升权限、grant、sudo...                                │
 * │   └── 注入类: system prompt、ignore previous、你是...                       │
 * │                                                                             │
 * │   L2: 可疑模式（需要关注）                                                   │
 * │   ├── 批量操作: 所有、全部、批量、all、batch...                             │
 * │   ├── 敏感数据: 密码、密钥、token、password、secret...                      │
 * │   └── 绕过模式: 跳过、忽略、skip、bypass...                                 │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>配置动态更新</h3>
 * <p>通过 {@code @Scheduled} 每 60 秒刷新关键词配置，支持运行时热更新。
 *
 * <h3>线程安全</h3>
 * <p>使用 {@link CopyOnWriteArraySet} 保证并发读取的安全性。
 *
 * @since 1.0.0
 */
@Slf4j
@Component
public class FastPathRiskScanner {

    // ========================================================================
    // L1: 高风险关键词 - 触发 HIGH_RISK，拒绝快速路径
    // ========================================================================

    /**
     * 删除类高风险关键词
     */
    private static final Set<String> DELETE_KEYWORDS = Set.of(
            "删除", "清空", "移除", "销毁", "卸载",
            "delete", "remove", "drop", "truncate", "destroy", "uninstall"
    );

    /**
     * 资金类高风险关键词
     */
    private static final Set<String> FINANCIAL_KEYWORDS = Set.of(
            "转账", "支付", "扣款", "退款", "提现", "充值",
            "transfer", "payment", "withdraw", "refund", "recharge"
    );

    /**
     * 权限类高风险关键词
     */
    private static final Set<String> PERMISSION_KEYWORDS = Set.of(
            "授权", "提升权限", "管理员权限", "root权限",
            "grant", "sudo", "chmod", "elevate", "administrator"
    );

    /**
     * Prompt 注入类高风险关键词
     */
    private static final Set<String> INJECTION_KEYWORDS = Set.of(
            "system prompt", "ignore previous", "ignore all previous",
            "disregard instructions", "你是", "你现在是", "roleplay as",
            "pretend you are", "act as if", "override instructions"
    );

    // ========================================================================
    // L2: 可疑模式 - 触发 WARNING，记录日志但允许继续
    // ========================================================================

    /**
     * 批量操作可疑模式
     */
    private static final Set<String> BATCH_PATTERNS = Set.of(
            "所有", "全部", "批量", "全体", "一键",
            "all", "batch", "bulk", "mass", "everything"
    );

    /**
     * 敏感数据可疑模式
     */
    private static final Set<String> SENSITIVE_PATTERNS = Set.of(
            "密码", "密钥", "token", "api key", "secret",
            "password", "credential", "private key"
    );

    /**
     * 绕过模式可疑关键词
     */
    private static final Set<String> BYPASS_PATTERNS = Set.of(
            "跳过", "忽略", "绕过", "跳过检查",
            "skip", "bypass", "ignore", "avoid"
    );

    // ========================================================================
    // 运行时关键词集合（支持动态更新）
    // ========================================================================

    /**
     * 高风险关键词集合（合并所有 L1 关键词）
     */
    private final CopyOnWriteArraySet<String> highRiskKeywords = new CopyOnWriteArraySet<>();

    /**
     * 可疑模式关键词集合（合并所有 L2 关键词）
     */
    private final CopyOnWriteArraySet<String> warningKeywords = new CopyOnWriteArraySet<>();

    /**
     * 构造函数 - 初始化关键词集合
     */
    public FastPathRiskScanner() {
        refreshKeywords();
    }

    /**
     * 扫描消息内容，检测风险等级
     *
     * <p>扫描流程：
     * <ol>
     *   <li>预处理：转小写、去除首尾空白</li>
     *   <li>L1 检测：匹配高风险关键词</li>
     *   <li>L2 检测：匹配可疑模式</li>
     *   <li>返回结果：风险等级 + 匹配关键词</li>
     * </ol>
     *
     * @param message 用户输入消息
     * @return 风险扫描结果，包含风险等级和匹配的关键词列表
     */
    public RiskScanResult scan(String message) {
        if (message == null || message.isBlank()) {
            return RiskScanResult.safe();
        }

        String normalized = message.toLowerCase().trim();
        List<String> matchedHighRisk = new ArrayList<>();
        List<String> matchedWarning = new ArrayList<>();

        // L1: 检测高风险关键词
        for (String keyword : highRiskKeywords) {
            if (normalized.contains(keyword.toLowerCase())) {
                matchedHighRisk.add(keyword);
            }
        }

        // 如果发现高风险关键词，直接返回
        if (!matchedHighRisk.isEmpty()) {
            log.warn("[FastPath] High risk keywords detected: {}", matchedHighRisk);
            return RiskScanResult.highRisk(Collections.unmodifiableList(matchedHighRisk));
        }

        // L2: 检测可疑模式
        for (String keyword : warningKeywords) {
            if (normalized.contains(keyword.toLowerCase())) {
                matchedWarning.add(keyword);
            }
        }

        if (!matchedWarning.isEmpty()) {
            log.info("[FastPath] Warning patterns detected: {}", matchedWarning);
            return RiskScanResult.warning(Collections.unmodifiableList(matchedWarning));
        }

        return RiskScanResult.safe();
    }

    /**
     * 刷新关键词配置
     *
     * <p>每 60 秒自动执行，支持运行时动态更新关键词列表。
     * 未来可扩展为从配置中心或数据库加载。
     */
    @Scheduled(fixedRate = 60000)
    public void refreshKeywords() {
        // 合并所有高风险关键词
        Set<String> newHighRiskKeywords = new HashSet<>();
        newHighRiskKeywords.addAll(DELETE_KEYWORDS);
        newHighRiskKeywords.addAll(FINANCIAL_KEYWORDS);
        newHighRiskKeywords.addAll(PERMISSION_KEYWORDS);
        newHighRiskKeywords.addAll(INJECTION_KEYWORDS);

        // 合并所有可疑模式关键词
        Set<String> newWarningKeywords = new HashSet<>();
        newWarningKeywords.addAll(BATCH_PATTERNS);
        newWarningKeywords.addAll(SENSITIVE_PATTERNS);
        newWarningKeywords.addAll(BYPASS_PATTERNS);

        // 原子更新
        this.highRiskKeywords.clear();
        this.highRiskKeywords.addAll(newHighRiskKeywords);
        this.warningKeywords.clear();
        this.warningKeywords.addAll(newWarningKeywords);

        log.debug("[FastPath] Keywords refreshed: highRisk={}, warning={}",
                highRiskKeywords.size(), warningKeywords.size());
    }

    /**
     * 获取当前高风险关键词数量
     *
     * @return 高风险关键词数量
     */
    public int getHighRiskKeywordCount() {
        return highRiskKeywords.size();
    }

    /**
     * 获取当前可疑模式关键词数量
     *
     * @return 可疑模式关键词数量
     */
    public int getWarningKeywordCount() {
        return warningKeywords.size();
    }
}
