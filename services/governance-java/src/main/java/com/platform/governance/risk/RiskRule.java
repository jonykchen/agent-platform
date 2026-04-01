package com.platform.governance.risk;

/**
 * 风险规则接口
 *
 * 【设计模式】策略模式 (Strategy Pattern)
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * 每个规则是一个独立的策略，可独立测试和扩展：
 *
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          规则继承结构                                       │
 * │                                                                             │
 * │                     ┌─────────────────┐                                    │
 * │                     │   RiskRule      │ (interface)                        │
 * │                     │   - getName()   │                                     │
 * │                     │   - getScore()  │                                     │
 * │                     │   - matches()  │                                     │
 * │                     └─────────────────┘                                    │
 * │                              ▲                                              │
 * │            ┌─────────────────┼─────────────────┐                          │
 * │            │                 │                 │                          │
 * │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐                │
 * │   │HighValue      │  │Sensitive      │  │HighRisk       │                │
 * │   │TransactionRule│  │FieldRule      │  │KeywordRule    │                │
 * │   │               │  │               │  │               │                │
 * │   │金额>=10000    │  │password/ssn   │  │delete/payment │                │
 * │   │+50分          │  │+40分          │  │+80分          │                │
 * │   └───────────────┘  └───────────────┘  └───────────────┘                │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 *
 * 【扩展方式】
 * 新增规则只需：
 * 1. 实现 RiskRule 接口
 * 2. 添加 @Component 注解（Spring 自动注入）
 * 3. RiskRuleEngine 会自动加载（通过 List<RiskRule> rules）
 *
 * 【方法说明】
 * - getName(): 规则名称，用于日志和审计
 * - getScore(): 匹配时返回的分数，用于计算总风险分
 * - matches(): 判断规则是否匹配当前工具调用
 */
public interface RiskRule {

    /**
     * 获取规则名称
     * @return 规则名称，如 "high_value_transaction"
     */
    String getName();

    /**
     * 获取规则分数
     * @return 匹配时返回的分数（0-100）
     */
    int getScore();

    /**
     * 判断规则是否匹配
     * @param toolName 工具名称
     * @param arguments 工具参数
     * @param tenantId 租户 ID
     * @return true 表示匹配，需要累加分数
     */
    boolean matches(String toolName, java.util.Map<String, Object> arguments, String tenantId);
}
