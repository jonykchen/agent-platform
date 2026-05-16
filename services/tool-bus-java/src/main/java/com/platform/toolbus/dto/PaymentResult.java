package com.platform.toolbus.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 支付结果 DTO
 *
 * <p>封装支付网关返回的支付处理结果，用于工具执行结果返回。
 *
 * <h2>数据来源</h2>
 * <p>由支付网关（如支付宝、微信支付）返回，通过 {@link com.platform.toolbus.client.PaymentGatewayClient} 封装。
 *
 * <h2>使用场景</h2>
 * <ul>
 *   <li>{@link com.platform.toolbus.tools.PaymentTool} 支付工具执行结果</li>
 *   <li>gRPC 响应中返回给 Orchestrator</li>
 * </ul>
 *
 * @see com.platform.toolbus.tools.PaymentTool
 * @see com.platform.toolbus.client.PaymentGatewayClient
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class PaymentResult {

    /**
     * 交易流水号
     *
     * <p>支付网关生成的唯一交易标识，格式如 {@code TXN20240515123456789}
     * <p>用于后续交易查询、退款等操作
     */
    private String transactionId;

    /**
     * 关联订单号
     *
     * <p>与支付请求中的订单号一致，用于关联业务订单
     * <p>格式由业务系统定义，如 {@code ORD20240515001}
     */
    private String orderId;

    /**
     * 支付金额
     *
     * <p>实际支付金额，单位为元（人民币）
     * <p>使用 {@link BigDecimal} 保证精度，避免浮点运算误差
     */
    private BigDecimal amount;

    /**
     * 支付状态
     *
     * <p>可选值：
     * <ul>
     *   <li>{@code SUCCESS} - 支付成功</li>
     *   <li>{@code PENDING} - 支付处理中</li>
     *   <li>{@code FAILED} - 支付失败</li>
     *   <li>{@code CANCELLED} - 支付取消</li>
     * </ul>
     */
    private String status;

    /**
     * 支付方式
     *
     * <p>实际使用的支付渠道，可选值：
     * <ul>
     *   <li>{@code ALIPAY} - 支付宝</li>
     *   <li>{@code WECHAT} - 微信支付</li>
     *   <li>{@code BANK_CARD} - 银行卡</li>
     *   <li>{@code CREDIT} - 信用支付</li>
     * </ul>
     */
    private String paymentMethod;

    /**
     * 处理时间
     *
     * <p>支付网关完成处理的时间，ISO 8601 格式
     * <p>示例：{@code 2024-05-15T10:30:45+08:00}
     */
    private String processedAt;
}
