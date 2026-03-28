package com.platform.toolbus.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 订单信息 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class OrderInfo {
    private String orderId;
    private String status;
    private BigDecimal amount;
    private Integer items;
    private String deliveryAddress;
    private String createdAt;
    private String updatedAt;
}
