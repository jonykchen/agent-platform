package com.platform.governance.risk;

/**
 * 风险规则接口
 */
public interface RiskRule {

    String getName();

    int getScore();

    boolean matches(String toolName, java.util.Map<String, Object> arguments, String tenantId);
}
