package com.platform.toolbus.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 用户信息 DTO
 *
 * <p>封装用户服务返回的用户详细信息，用于工具执行结果返回。
 *
 * <h2>数据来源</h2>
 * <p>由用户服务（CRM/会员系统）返回，通过 {@link com.platform.toolbus.client.UserServiceClient} 封装。
 *
 * <h2>使用场景</h2>
 * <ul>
 *   <li>{@link com.platform.toolbus.tools.UserInfoTool} 用户查询工具执行结果</li>
 *   <li>风险评估时的用户画像信息</li>
 *   <li>gRPC 响应中返回给 Orchestrator</li>
 * </ul>
 *
 * @see com.platform.toolbus.tools.UserInfoTool
 * @see com.platform.toolbus.client.UserServiceClient
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserInfo {

    /**
     * 用户 ID
     *
     * <p>用户唯一标识，由用户服务生成
     * <p>格式如 {@code user_abc123} 或 UUID 格式
     */
    private String id;

    /**
     * 用户姓名
     *
     * <p>用户的真实姓名或昵称
     * <p>敏感信息，需遵守隐私保护规范
     */
    private String name;

    /**
     * 用户邮箱
     *
     * <p>用户注册邮箱，用于通知等场景
     * <p>格式符合标准邮箱格式，如 {@code user@example.com}
     */
    private String email;

    /**
     * 用户手机号
     *
     * <p>用户绑定手机号，用于短信通知、身份验证
     * <p>格式：中国大陆手机号为 11 位数字，如 {@code 13800138000}
     * <p>敏感信息，输出时需脱敏处理（中间 4 位）
     */
    private String phone;

    /**
     * 用户等级
     *
     * <p>会员等级或用户分层标识，可选值：
     * <ul>
     *   <li>{@code BRONZE} - 铜牌会员</li>
     *   <li>{@code SILVER} - 银牌会员</li>
     *   <li>{@code GOLD} - 金牌会员</li>
     *   <li>{@code PLATINUM} - 白金会员</li>
     *   <li>{@code DIAMOND} - 钻石会员</li>
     * </ul>
     */
    private String level;

    /**
     * 注册日期
     *
     * <p>用户首次注册时间，ISO 8601 格式
     * <p>示例：{@code 2023-06-15}
     */
    private String registerDate;

    /**
     * 历史订单总数
     *
     * <p>用户累计完成的订单数量，用于用户价值评估
     * <p>仅统计已完成状态的订单
     */
    private Integer totalOrders;
}
