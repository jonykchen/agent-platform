package com.platform.governance.notification;

import com.platform.governance.approval.ApprovalTask;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

/**
 * 通知服务 - 发送审批请求和发布审批结果
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final KafkaTemplate<String, String> kafkaTemplate;

    private static final String APPROVAL_TOPIC = "agent-platform.approval";

    /**
     * 发送审批请求通知
     */
    public void sendApprovalRequest(ApprovalTask task) {
        // TODO: 集成企业微信/钉钉/邮件通知
        log.info("Sending approval request: approvalId={}, requester={}",
                task.getId(), task.getRequesterId());
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
}
