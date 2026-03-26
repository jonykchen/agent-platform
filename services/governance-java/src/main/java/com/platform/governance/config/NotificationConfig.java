package com.platform.governance.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * 通知配置
 *
 * 支持企业微信、钉钉、邮件三种渠道。
 */
@Data
@Component
@ConfigurationProperties(prefix = "notification")
public class NotificationConfig {

    /** 企业微信 Webhook URL */
    private String wecomWebhook;

    /** 钉钉 Webhook URL */
    private String dingtalkWebhook;

    /** 是否启用邮件通知 */
    private boolean emailEnabled = false;

    /** SMTP 服务器 */
    private String smtpHost;

    /** SMTP 端口 */
    private int smtpPort = 587;

    /** 发件人邮箱 */
    private String smtpFrom;

    /** SMTP 用户名 */
    private String smtpUsername;

    /** SMTP 密码 */
    private String smtpPassword;
}