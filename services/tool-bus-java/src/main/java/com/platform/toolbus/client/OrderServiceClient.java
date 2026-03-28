package com.platform.toolbus.client;

import com.platform.toolbus.dto.OrderInfo;

/**
 * 订单服务客户端接口
 *
 * 支持通过配置切换 Mock 和真实实现
 */
public interface OrderServiceClient {

    /**
     * 查询订单信息
     *
     * @param orderId 订单ID
     * @return 订单信息，不存在返回 null
     */
    OrderInfo getOrderInfo(String orderId);

    /**
     * 检查服务是否可用
     *
     * @return true 表示真实服务已连接
     */
    boolean isRealService();
}