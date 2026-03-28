package com.platform.governance.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.JavaMailSenderImpl;

import java.util.Properties;

/**
 * 邮件发送配置
 *
 * 配置示例：
 * mail:
 *   host: smtp.example.com
 *   port: 587
 *   username: noreply@example.com
 *   password: ${MAIL_PASSWORD}
 *   from: noreply@agent-platform.com
 *   tls-enabled: true
 */
@Configuration
@ConfigurationProperties(prefix = "mail")
@Data
public class MailConfig {

    private String host;
    private int port = 587;
    private String username;
    private String password;
    private String from = "noreply@agent-platform.com";
    private boolean tlsEnabled = true;
    private boolean enabled = false;

    @Bean
    public JavaMailSender javaMailSender() {
        JavaMailSenderImpl sender = new JavaMailSenderImpl();
        sender.setHost(host);
        sender.setPort(port);
        sender.setUsername(username);
        sender.setPassword(password);

        Properties props = sender.getJavaMailProperties();
        props.put("mail.transport.protocol", "smtp");
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.starttls.enable", String.valueOf(tlsEnabled));
        props.put("mail.smtp.connectiontimeout", "5000");
        props.put("mail.smtp.timeout", "10000");

        return sender;
    }
}
