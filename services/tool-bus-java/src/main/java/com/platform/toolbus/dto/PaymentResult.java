package com.platform.toolbus.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 支付结果 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PaymentResult {
    private String transactionId;
    private String orderId;
    private BigDecimal amount;
    private String status;
    private String paymentMethod;
    private String processedAt;
}
