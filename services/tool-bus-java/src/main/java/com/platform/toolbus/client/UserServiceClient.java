package com.platform.toolbus.client;

import com.platform.toolbus.dto.UserInfo;

/**
 * 用户服务客户端接口
 *
 * 支持通过配置切换 Mock 和真实实现
 */
public interface UserServiceClient {

    /**
     * 查询用户信息
     *
     * @param userId 用户ID
     * @return 用户信息，不存在返回 null
     */
    UserInfo getUserInfo(String userId);

    /**
     * 检查服务是否可用
     *
     * @return true 表示真实服务已连接
     */
    boolean isRealService();
}