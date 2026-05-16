package com.platform.gateway.service;

import java.util.Collections;
import java.util.List;

/**
 * 风险扫描结果
 *
 * <p>包含风险等级和匹配的关键词列表。
 *
 * <h3>使用示例</h3>
 * <pre>{@code
 * RiskScanResult result = riskScanner.scan(message);
 * if (result.riskLevel() == RiskLevel.HIGH_RISK) {
 *     // 拒绝快速路径
 * }
 * }</pre>
 *
 * @param riskLevel 风险等级
 * @param matchedKeywords 匹配的关键词列表
 * @since 1.0.0
 */
public record RiskScanResult(
        RiskLevel riskLevel,
        List<String> matchedKeywords
) {

    /**
     * 创建安全结果
     *
     * @return 风险等级为 SAFE 的空结果
     */
    public static RiskScanResult safe() {
        return new RiskScanResult(RiskLevel.SAFE, Collections.emptyList());
    }

    /**
     * 创建警告结果
     *
     * @param keywords 匹配的可疑关键词
     * @return 风险等级为 WARNING 的结果
     */
    public static RiskScanResult warning(List<String> keywords) {
        return new RiskScanResult(RiskLevel.WARNING, keywords);
    }

    /**
     * 创建高风险结果
     *
     * @param keywords 匹配的高风险关键词
     * @return 风险等级为 HIGH_RISK 的结果
     */
    public static RiskScanResult highRisk(List<String> keywords) {
        return new RiskScanResult(RiskLevel.HIGH_RISK, keywords);
    }

    /**
     * 判断是否为高风险
     *
     * @return 如果风险等级为 HIGH_RISK 返回 true
     */
    public boolean isHighRisk() {
        return riskLevel == RiskLevel.HIGH_RISK;
    }

    /**
     * 判断是否安全
     *
     * @return 如果风险等级为 SAFE 返回 true
     */
    public boolean isSafe() {
        return riskLevel == RiskLevel.SAFE;
    }
}
