package com.platform.governance.notification;

import com.platform.governance.approval.ApprovalTask;
import com.platform.governance.config.MailConfig;
import com.platform.governance.config.NotificationConfig;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.mail.javamail.JavaMailSender;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

/**
 * NotificationService 单元测试
 */
@ExtendWith(MockitoExtension.class)
class NotificationServiceTest {

    @Mock
    private KafkaTemplate<String, String> kafkaTemplate;

    @Mock
    private NotificationConfig notificationConfig;

    @Mock
    private MailConfig mailConfig;

    @Mock
    private JavaMailSender mailSender;

    private NotificationService notificationService;

    @BeforeEach
    void setUp() {
        lenient().when(notificationConfig.getWecomWebhook()).thenReturn(null);
        lenient().when(notificationConfig.getDingtalkWebhook()).thenReturn(null);
        lenient().when(notificationConfig.isEmailEnabled()).thenReturn(false);
        notificationService = new NotificationService(kafkaTemplate, notificationConfig, mailConfig, mailSender);
    }

    @Test
    @DisplayName("发送审批请求应记录日志")
    void sendApprovalRequest_logsRequest() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .requesterId("user_001")
                .build();

        // When
        notificationService.sendApprovalRequest(task);

        // Then - 方法应正常执行，无异常抛出
        // 目前仅记录日志，不验证其他行为
    }

    @Test
    @DisplayName("发布审批结果-批准应发送Kafka消息")
    void publishApprovalResult_approved_sendsKafkaMessage() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .runId("run_456")
                .tenantId("tenant_001")
                .status("approved")
                .build();

        ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

        // When
        notificationService.publishApprovalResult(task);

        // Then
        verify(kafkaTemplate).send(
                eq("agent-platform.approval"),
                eq("approval_123"),
                messageCaptor.capture());

        String message = messageCaptor.getValue();
        assertTrue(message.contains("\"event_type\":\"approval.approved\""));
        assertTrue(message.contains("\"approval_id\":\"approval_123\""));
        assertTrue(message.contains("\"run_id\":\"run_456\""));
        assertTrue(message.contains("\"tenant_id\":\"tenant_001\""));
    }

    @Test
    @DisplayName("发布审批结果-拒绝应发送Kafka消息")
    void publishApprovalResult_rejected_sendsKafkaMessage() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_456")
                .runId("run_789")
                .tenantId("tenant_002")
                .status("rejected")
                .build();

        ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

        // When
        notificationService.publishApprovalResult(task);

        // Then
        verify(kafkaTemplate).send(
                eq("agent-platform.approval"),
                eq("approval_456"),
                messageCaptor.capture());

        String message = messageCaptor.getValue();
        assertTrue(message.contains("\"event_type\":\"approval.rejected\""));
        assertTrue(message.contains("\"approval_id\":\"approval_456\""));
        assertTrue(message.contains("\"run_id\":\"run_789\""));
        assertTrue(message.contains("\"tenant_id\":\"tenant_002\""));
    }

    @Test
    @DisplayName("发布审批结果应发送到正确的Topic")
    void publishApprovalResult_usesCorrectTopic() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .runId("run_456")
                .tenantId("tenant_001")
                .status("approved")
                .build();

        // When
        notificationService.publishApprovalResult(task);

        // Then
        verify(kafkaTemplate).send(
                eq("agent-platform.approval"),
                anyString(),
                anyString());
    }

    @Test
    @DisplayName("发布审批结果应使用审批ID作为消息Key")
    void publishApprovalResult_usesApprovalIdAsKey() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("my_approval_id")
                .runId("run_456")
                .tenantId("tenant_001")
                .status("approved")
                .build();

        // When
        notificationService.publishApprovalResult(task);

        // Then
        verify(kafkaTemplate).send(
                anyString(),
                eq("my_approval_id"),
                anyString());
    }

    @Test
    @DisplayName("消息格式应为有效JSON")
    void publishApprovalResult_messageIsValidJson() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .runId("run_456")
                .tenantId("tenant_001")
                .status("approved")
                .build();

        ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

        // When
        notificationService.publishApprovalResult(task);

        // Then
        verify(kafkaTemplate).send(anyString(), anyString(), messageCaptor.capture());

        String message = messageCaptor.getValue();
        // 验证JSON格式基本结构
        assertTrue(message.startsWith("{"));
        assertTrue(message.endsWith("}"));
        // 验证包含必要字段
        assertTrue(message.contains("event_type"));
        assertTrue(message.contains("approval_id"));
        assertTrue(message.contains("run_id"));
        assertTrue(message.contains("tenant_id"));
    }

    @Test
    @DisplayName("发送审批请求对空任务应正常处理")
    void sendApprovalRequest_handlesTaskWithNullFields() {
        // Given
        ApprovalTask task = ApprovalTask.builder().build();

        // When & Then - 不应抛出异常
        assertDoesNotThrow(() -> notificationService.sendApprovalRequest(task));
    }

    @Test
    @DisplayName("发布审批结果对已过期任务应正常处理")
    void publishApprovalResult_handlesExpiredTask() {
        // Given
        ApprovalTask task = ApprovalTask.builder()
                .id("approval_123")
                .runId("run_456")
                .tenantId("tenant_001")
                .status("expired")
                .build();

        ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

        // When
        notificationService.publishApprovalResult(task);

        // Then
        verify(kafkaTemplate).send(anyString(), anyString(), messageCaptor.capture());
        assertTrue(messageCaptor.getValue().contains("approval.expired"));
    }

    @Test
    @DisplayName("多次发送应调用Kafka多次")
    void publishApprovalResult_multipleCalls_sendsMultipleMessages() {
        // Given
        ApprovalTask task1 = ApprovalTask.builder()
                .id("approval_1")
                .runId("run_1")
                .tenantId("tenant_001")
                .status("approved")
                .build();

        ApprovalTask task2 = ApprovalTask.builder()
                .id("approval_2")
                .runId("run_2")
                .tenantId("tenant_001")
                .status("rejected")
                .build();

        // When
        notificationService.publishApprovalResult(task1);
        notificationService.publishApprovalResult(task2);

        // Then
        verify(kafkaTemplate, times(2)).send(anyString(), anyString(), anyString());
    }

    @Test
    @DisplayName("事件类型应根据任务状态生成")
    void publishApprovalResult_eventTypeMatchesStatus() {
        // Given
        String[] statuses = {"approved", "rejected", "expired", "pending"};

        for (String status : statuses) {
            // Reset mock for each iteration
            reset(kafkaTemplate);

            ApprovalTask task = ApprovalTask.builder()
                    .id("approval_" + status)
                    .runId("run_test")
                    .tenantId("tenant_001")
                    .status(status)
                    .build();

            ArgumentCaptor<String> messageCaptor = ArgumentCaptor.forClass(String.class);

            // When
            notificationService.publishApprovalResult(task);

            // Then
            verify(kafkaTemplate).send(anyString(), anyString(), messageCaptor.capture());
            assertTrue(messageCaptor.getValue().contains("approval." + status));
        }
    }
}
