package com.platform.toolbus.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

/**
 * 订单信息 DTO
 *
 * <p>封装订单服务返回的订单详情，用于工具执行结果返回。
 *
 * <h2>数据来源</h2>
 * <p>由订单服务（OMS）返回，通过 {@link com.platform.toolbus.client.OrderServiceClient} 封装。
 *
 * <h2>使用场景</h2>
 * <ul>
 *   <li>{@link com.platform.toolbus.tools.OrderQueryTool} 订单查询工具执行结果</li>
 *   <li>支付前订单状态校验</li>
 *   <li>风险评估时的订单信息</li>
 *   <li>gRPC 响应中返回给 Orchestrator</li>
 * </ul>
 *
 * @see com.platform.toolbus.tools.OrderQueryTool
 * @see com.platform.toolbus.client.OrderServiceClient
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class OrderInfo {

    /**
     * 订单号
     *
     * <p>订单唯一标识，由订单系统生成
     * <p>格式如 {@code ORD20240515001} 或 {@code 2024051512345678}
     */
    private String orderId;

    /**
     * 订单状态
     *
     * <p>订单当前状态，可选值：
     * <ul>
     *   <li>{@code PENDING} - 待支付</li>
     *   <li>{@code PAID} - 已支付</li>
     *   <li>{@code SHIPPING} - 配送中</li>
     *   <li>{@code DELIVERED} - 已送达</li>
     *   <li>{@code CANCELLED} - 已取消</li>
     *   <li>{@code REFUNDED} - 已退款</li>
     * </ul>
     */
    private String status;

    /**
     * 订单金额
     *
     * <p>订单总金额，单位为元（人民币）
     * <p>使用 {@link BigDecimal} 保证精度，避免浮点运算误差
     * <p>包含商品金额、运费、优惠抵扣后的最终金额
     */
    private BigDecimal amount;

    /**
     * 商品数量
     *
     * <p>订单中包含的商品总数量（SKU 级别统计）
     */
    private Integer items;

    /**
     * 配送地址
     *
     * <p>订单收货地址，完整地址字符串
     * <p>格式如 {@code 北京市朝阳区xxx街道xxx号}
     * <p>敏感信息，输出时可根据需要脱敏处理
     */
    private String deliveryAddress;

    /**
     * 创建时间
     *
     * <p>订单创建时间，ISO 8601 格式
     * <p>示例：{@code 2024-05-15T10:30:00+08:00}
     */
    private String createdAt;

    /**
     * 更新时间
     *
     * <p>订单最后更新时间（状态变更、金额修改等），ISO 8601 格式
     * <p>示例：{@code 2024-05-15T14:20:30+08:00}
     */
    private String updatedAt;
}
