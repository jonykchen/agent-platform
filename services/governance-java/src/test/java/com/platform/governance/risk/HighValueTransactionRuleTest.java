package com.platform.governance.risk;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

/**
 * HighValueTransactionRule 单元测试
 */
class HighValueTransactionRuleTest {

    private HighValueTransactionRule rule;

    @BeforeEach
    void setUp() {
        rule = new HighValueTransactionRule();
    }

    @Test
    @DisplayName("规则名称应为high_value_transaction")
    void getName_returnsCorrectName() {
        assertEquals("high_value_transaction", rule.getName());
    }

    @Test
    @DisplayName("规则分数应为50")
    void getScore_returnsCorrectScore() {
        assertEquals(50, rule.getScore());
    }

    @Test
    @DisplayName("当工具名不包含payment或transfer时应不匹配")
    void matches_nonPaymentOrTransferTool_returnsFalse() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 15000.0);

        assertFalse(rule.matches("query_balance", arguments, "tenant_001"));
        assertFalse(rule.matches("create_order", arguments, "tenant_001"));
        assertFalse(rule.matches("update_user", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当工具名包含payment且金额>=10000时应匹配")
    void matches_paymentToolWithHighAmount_returnsTrue() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 10000.0);

        assertTrue(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当工具名包含transfer且金额>=10000时应匹配")
    void matches_transferToolWithHighAmount_returnsTrue() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 15000.0);

        assertTrue(rule.matches("bank_transfer", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当金额等于阈值10000时应匹配")
    void matches_amountEqualsThreshold_returnsTrue() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 10000.0);

        assertTrue(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当金额小于阈值10000时应不匹配")
    void matches_amountBelowThreshold_returnsFalse() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 9999.99);

        assertFalse(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当金额远大于阈值时应匹配")
    void matches_amountFarAboveThreshold_returnsTrue() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 1000000.0);

        assertTrue(rule.matches("bank_transfer", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当参数中没有amount时应不匹配")
    void matches_noAmountArgument_returnsFalse() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("account", "123456");

        assertFalse(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当amount为Integer类型时应正确处理")
    void matches_amountAsInteger_handlesCorrectly() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 15000); // Integer

        assertTrue(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当amount为Long类型时应正确处理")
    void matches_amountAsLong_handlesCorrectly() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 15000L); // Long

        assertTrue(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当amount为Double类型时应正确处理")
    void matches_amountAsDouble_handlesCorrectly() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 12000.50); // Double

        assertTrue(rule.matches("bank_transfer", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当amount为Float类型时应正确处理")
    void matches_amountAsFloat_handlesCorrectly() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 12000.50f); // Float

        assertTrue(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当amount为字符串类型时应不匹配")
    void matches_amountAsString_returnsFalse() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", "15000");

        assertFalse(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当amount为null时应不匹配")
    void matches_amountAsNull_returnsFalse() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", null);

        assertFalse(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当参数为空Map时应不匹配")
    void matches_emptyArguments_returnsFalse() {
        Map<String, Object> arguments = new HashMap<>();

        assertFalse(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("应忽略租户ID")
    void matches_differentTenantIds_sameBehavior() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 15000.0);

        assertTrue(rule.matches("process_payment", arguments, "tenant_001"));
        assertTrue(rule.matches("process_payment", arguments, "tenant_002"));
        assertTrue(rule.matches("process_payment", arguments, null));
    }

    @Test
    @DisplayName("工具名部分匹配payment即可")
    void matches_toolNameContainsPayment_returnsTrue() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 15000.0);

        assertTrue(rule.matches("make_payment", arguments, "tenant_001"));
        assertTrue(rule.matches("payment_process", arguments, "tenant_001"));
        assertTrue(rule.matches("autopayment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("工具名部分匹配transfer即可")
    void matches_toolNameContainsTransfer_returnsTrue() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 15000.0);

        assertTrue(rule.matches("make_transfer", arguments, "tenant_001"));
        assertTrue(rule.matches("transfer_money", arguments, "tenant_001"));
        assertTrue(rule.matches("interbank_transfer", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当金额为负数时应匹配")
    void matches_negativeAmount_handlesCorrectly() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", -15000.0);

        // 负数的绝对值大于阈值，但在实际业务中可能需要额外处理
        assertTrue(rule.matches("process_payment", arguments, "tenant_001"));
    }

    @Test
    @DisplayName("当金额为0时应不匹配")
    void matches_zeroAmount_returnsFalse() {
        Map<String, Object> arguments = new HashMap<>();
        arguments.put("amount", 0.0);

        assertFalse(rule.matches("process_payment", arguments, "tenant_001"));
    }
}
