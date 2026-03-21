package com.platform.governance.risk;

import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 风险评估结果测试
 */
class RiskAssessmentTest {

    @Test
    void riskAssessment_shouldBuildCorrectly() {
        Map<String, Object> details = new HashMap<>();
        details.put("amount", 10000);
        details.put("threshold", 5000);

        RiskAssessment assessment = RiskAssessment.builder()
                .toolName("process_payment")
                .tenantId("tenant-001")
                .riskLevel("high")
                .riskScore(50)
                .matchedRule("high_value_transaction")
                .requiresApproval(true)
                .details(details)
                .build();

        assertEquals("process_payment", assessment.getToolName());
        assertEquals("tenant-001", assessment.getTenantId());
        assertEquals("high", assessment.getRiskLevel());
        assertEquals(50, assessment.getRiskScore());
        assertEquals("high_value_transaction", assessment.getMatchedRule());
        assertTrue(assessment.isRequiresApproval());
        assertEquals(10000, assessment.getDetails().get("amount"));
    }

    @Test
    void riskAssessment_shouldHaveDefaultValues() {
        RiskAssessment assessment = RiskAssessment.builder().build();

        assertNull(assessment.getToolName());
        assertNull(assessment.getRiskLevel());
        assertFalse(assessment.isRequiresApproval());
    }

    @Test
    void riskAssessment_shouldAllowModification() {
        RiskAssessment assessment = RiskAssessment.builder()
                .riskLevel("low")
                .build();

        assessment.setRiskLevel("medium");
        assessment.setRequiresApproval(true);

        assertEquals("medium", assessment.getRiskLevel());
        assertTrue(assessment.isRequiresApproval());
    }
}