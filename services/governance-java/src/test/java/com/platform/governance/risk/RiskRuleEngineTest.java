package com.platform.governance.risk;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * RiskRuleEngine 单元测试
 */
@ExtendWith(MockitoExtension.class)
class RiskRuleEngineTest {

    @Mock
    private RiskRule mockRule1;

    @Mock
    private RiskRule mockRule2;

    private RiskRuleEngine ruleEngine;

    @BeforeEach
    void setUp() {
        ruleEngine = new RiskRuleEngine(Arrays.asList(mockRule1, mockRule2));
    }

    @Test
    @DisplayName("当没有规则匹配时，应返回低风险")
    void assess_noRulesMatched_returnsLowRisk() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(false);
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 100.0);

        // When
        RiskAssessment result = ruleEngine.assess("query_balance", arguments, "tenant_001");

        // Then
        assertEquals("low", result.getRiskLevel());
        assertEquals(0, result.getRiskScore());
        assertFalse(result.isRequiresApproval());
        assertNull(result.getMatchedRule());
    }

    @Test
    @DisplayName("当单个规则匹配且分数为30时，应返回中风险")
    void assess_singleRuleMatches_score30_returnsMediumRisk() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(true);
        when(mockRule1.getScore()).thenReturn(30);
        when(mockRule1.getName()).thenReturn("test_rule");
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("some_tool", arguments, "tenant_001");

        // Then
        assertEquals("medium", result.getRiskLevel());
        assertEquals(30, result.getRiskScore());
        assertTrue(result.isRequiresApproval());
        assertEquals("test_rule", result.getMatchedRule());
    }

    @Test
    @DisplayName("当多个规则匹配时，应累加分数")
    void assess_multipleRulesMatched_accumulatesScore() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(true);
        when(mockRule1.getScore()).thenReturn(30);
        when(mockRule1.getName()).thenReturn("rule_1");
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(true);
        when(mockRule2.getScore()).thenReturn(25);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("some_tool", arguments, "tenant_001");

        // Then
        assertEquals("high", result.getRiskLevel());
        assertEquals(55, result.getRiskScore());
        assertTrue(result.isRequiresApproval());
    }

    @Test
    @DisplayName("当分数>=80时应返回critical风险等级")
    void assess_score80_returnsCriticalRisk() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(true);
        when(mockRule1.getScore()).thenReturn(50);
        when(mockRule1.getName()).thenReturn("critical_rule");
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(true);
        when(mockRule2.getScore()).thenReturn(30);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("some_tool", arguments, "tenant_001");

        // Then
        assertEquals("critical", result.getRiskLevel());
        assertEquals(80, result.getRiskScore());
        assertTrue(result.isRequiresApproval());
    }

    @Test
    @DisplayName("当工具名包含delete时应需要审批")
    void assess_deleteTool_requiresApproval() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(false);
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("delete_user", arguments, "tenant_001");

        // Then
        assertTrue(result.isRequiresApproval());
        assertEquals("delete_user", result.getToolName());
    }

    @Test
    @DisplayName("当工具名包含payment时应需要审批")
    void assess_paymentTool_requiresApproval() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(false);
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("process_payment", arguments, "tenant_001");

        // Then
        assertTrue(result.isRequiresApproval());
    }

    @Test
    @DisplayName("当工具名包含transfer时应需要审批")
    void assess_transferTool_requiresApproval() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(false);
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("bank_transfer", arguments, "tenant_001");

        // Then
        assertTrue(result.isRequiresApproval());
    }

    @Test
    @DisplayName("当工具名包含remove时应需要审批")
    void assess_removeTool_requiresApproval() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(false);
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("remove_account", arguments, "tenant_001");

        // Then
        assertTrue(result.isRequiresApproval());
    }

    @Test
    @DisplayName("应正确记录租户ID")
    void assess_recordsTenantId() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(false);
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("some_tool", arguments, "tenant_123");

        // Then
        assertEquals("tenant_123", result.getTenantId());
    }

    @Test
    @DisplayName("当规则列表为空时应返回低风险")
    void assess_emptyRuleList_returnsLowRisk() {
        // Given
        RiskRuleEngine emptyEngine = new RiskRuleEngine(Collections.emptyList());

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = emptyEngine.assess("normal_tool", arguments, "tenant_001");

        // Then
        assertEquals("low", result.getRiskLevel());
        assertEquals(0, result.getRiskScore());
        assertFalse(result.isRequiresApproval());
    }

    @Test
    @DisplayName("当分数在50-79范围时应返回high风险等级")
    void assess_scoreBetween50And79_returnsHighRisk() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(true);
        when(mockRule1.getScore()).thenReturn(50);
        when(mockRule1.getName()).thenReturn("high_risk_rule");
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("some_tool", arguments, "tenant_001");

        // Then
        assertEquals("high", result.getRiskLevel());
        assertEquals(50, result.getRiskScore());
    }

    @Test
    @DisplayName("当分数在30-49范围时应返回medium风险等级")
    void assess_scoreBetween30And49_returnsMediumRisk() {
        // Given
        when(mockRule1.matches(anyString(), anyMap(), anyString())).thenReturn(true);
        when(mockRule1.getScore()).thenReturn(40);
        when(mockRule1.getName()).thenReturn("medium_risk_rule");
        when(mockRule2.matches(anyString(), anyMap(), anyString())).thenReturn(false);

        Map<String, Object> arguments = new HashMap<>();

        // When
        RiskAssessment result = ruleEngine.assess("some_tool", arguments, "tenant_001");

        // Then
        assertEquals("medium", result.getRiskLevel());
        assertEquals(40, result.getRiskScore());
    }
}
