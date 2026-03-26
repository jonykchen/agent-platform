package com.platform.governance.notification;

import com.platform.governance.approval.ApprovalTask;
import com.platform.governance.config.NotificationConfig;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.Map;

/**
 * 通知服务 - 企业微信/钉钉/邮件通知
 *
 * 【支持渠道】
 * - 企业微信：Webhook 机器人
 * - 钉钉：Webhook 机器人
 * - 邮件：SMTP 发送
 *
 * 【通知类型】
 * - 审批请求：通知审批人
 * - 审批结果：通知申请人
 * - 系统告警：通知运维团队
 *
 * 【配置方式】
 * 通过 application.yml 配置：
 * notification:
 *   wecom-webhook: https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
 *   dingtalk-webhook: https://oapi.dingtalk.com/robot/send?access_token=xxx
 *   email-enabled: true
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final KafkaTemplate<String, String> kafkaTemplate;
    private final NotificationConfig notificationConfig;
    private final RestTemplate restTemplate = new RestTemplate();

    private static final String APPROVAL_TOPIC = "agent-platform.approval";

    /**
     * 发送审批请求通知
     *
     * 【通知内容】
     * - 审批任务 ID
     * - 申请人
     * - 工具名称
     * - 审批原因
     * - 截止时间
     */
    public void sendApprovalRequest(ApprovalTask task) {
        log.info("Sending approval request: approvalId={}, requester={}",
                task.getId(), task.getRequesterId());

        String message = buildApprovalRequestMessage(task);

        // 企业微信通知
        if (notificationConfig.getWecomWebhook() != null) {
            sendWecomNotification(message);
        }

        // 钉钉通知
        if (notificationConfig.getDingtalkWebhook() != null) {
            sendDingtalkNotification(message);
        }

        // 邮件通知
        if (notificationConfig.isEmailEnabled() && task.getApproverEmail() != null) {
            sendEmailNotification(
                task.getApproverEmail(),
                "审批请求：" + task.getToolName(),
                message
            );
        }
    }

    /**
     * 发送审批结果通知
     */
    public void sendApprovalResult(ApprovalTask task) {
        log.info("Sending approval result: approvalId={}, status={}",
                task.getId(), task.getStatus());

        String message = buildApprovalResultMessage(task);

        // 企业微信通知
        if (notificationConfig.getWecomWebhook() != null) {
            sendWecomNotification(message);
        }

        // 钉钉通知
        if (notificationConfig.getDingtalkWebhook() != null) {
            sendDingtalkNotification(message);
        }
    }

    /**
     * 发布审批结果事件（供 Orchestrator 消费）
     */
    public void publishApprovalResult(ApprovalTask task) {
        String event = String.format(
                "{\"event_type\":\"approval.%s\",\"approval_id\":\"%s\",\"run_id\":\"%s\",\"tenant_id\":\"%s\"}",
                task.getStatus(), task.getId(), task.getRunId(), task.getTenantId()
        );

        kafkaTemplate.send(APPROVAL_TOPIC, task.getId(), event);

        log.info("Published approval result: approvalId={}, status={}",
                task.getId(), task.getStatus());
    }

    /**
     * 企业微信 Webhook 发送
     *
     * API 格式：https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
     */
    private void sendWecomNotification(String content) {
        try {
            Map<String, Object> body = new HashMap<>();
            body.put("msgtype", "text");
            body.put("text", Map.of("content", content));

            restTemplate.postForEntity(
                notificationConfig.getWecomWebhook(),
                body,
                String.class
            );

            log.debug("Wecom notification sent successfully");

        } catch (Exception e) {
            log.warn("Wecom notification failed: {}", e.getMessage());
        }
    }

    /**
     * 钉钉 Webhook 发送
     *
     * API 格式：https://oapi.dingtalk.com/robot/send?access_token=xxx
     */
    private void sendDingtalkNotification(String content) {
        try {
            Map<String, Object> body = new HashMap<>();
            body.put("msgtype", "text");
            body.put("text", Map.of("content", content));

            restTemplate.postForEntity(
                notificationConfig.getDingtalkWebhook(),
                body,
                String.class
            );

            log.debug("Dingtalk notification sent successfully");

        } catch (Exception e) {
            log.warn("Dingtalk notification failed: {}", e.getMessage());
        }
    }

    /**
     * 邮件发送（SMTP）
     *
     * TODO: 实现邮件发送逻辑
     */
    private void sendEmailNotification(String to, String subject, String content) {
        log.info("Sending email: to={}, subject={}", to, subject);
        // TODO: 使用 JavaMail 或第三方服务发送邮件
    }

    /**
     * 构建审批请求消息
     */
    private String buildApprovalRequestMessage(ApprovalTask task) {
        return String.format(
            "【审批请求】\n" +
            "审批ID：%s\n" +
            "申请人：%s\n" +
            "工具名称：%s\n" +
            "审批原因：%s\n" +
            "请尽快处理。",
            task.getId(),
            task.getRequesterId(),
            task.getToolName(),
            task.getApprovalReason()
        );
    }

    /**
     * 构建审批结果消息
     */
    private String buildApprovalResultMessage(ApprovalTask task) {
        String statusText = task.getStatus().equals("approved") ? "已通过" : "已拒绝";
        return String.format(
            "【审批结果】\n" +
            "审批ID：%s\n" +
            "状态：%s\n" +
            "处理人：%s\n" +
            "处理时间：%s",
            task.getId(),
            statusText,
            task.getApproverId(),
            task.getProcessedAt()
        );
    }
}