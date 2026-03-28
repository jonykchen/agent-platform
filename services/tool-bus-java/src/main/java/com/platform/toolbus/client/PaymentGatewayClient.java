package com.platform.toolbus.client;

import com.platform.toolbus.dto.PaymentResult;

import java.math.BigDecimal;

/**
 * 支付网关客户端接口
 *
 * 支持通过配置切换 Mock 和真实实现
 */
public interface PaymentGatewayClient {

    /**
     * 处理支付
     *
     * @param orderId 订单ID
     * @param amount 金额
     * @param paymentMethod 支付方式
     * @return 支付结果
     */
    PaymentResult processPayment(String orderId, BigDecimal amount, String paymentMethod);

    /**
     * 检查服务是否可用
     *
     * @return true 表示真实服务已连接
     */
    boolean isRealService();
}