package com.platform.gateway.service;

/**
 * 风险等级枚举
 *
 * <p>用于快速路径风险扫描结果的风险等级分类。
 *
 * <h3>风险等级定义</h3>
 * <table border="1">
 *   <tr><th>等级</th><th>描述</th><th>处理策略</th></tr>
 *   <tr><td>SAFE</td><td>安全，无风险关键词</td><td>允许快速路径</td></tr>
 *   <tr><td>WARNING</td><td>警告，包含可疑模式</td><td>允许快速路径，记录日志</td></tr>
 *   <tr><td>HIGH_RISK</td><td>高风险，包含危险关键词</td><td>拒绝快速路径，强制完整编排</td></tr>
 * </table>
 *
 * @since 1.0.0
 */
public enum RiskLevel {

    /**
     * 安全 - 无风险关键词匹配
     */
    SAFE,

    /**
     * 警告 - 包含可疑模式，需关注但可继续
     */
    WARNING,

    /**
     * 高风险 - 包含危险关键词，必须走完整编排
     */
    HIGH_RISK
}
