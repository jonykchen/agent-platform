package com.platform.gateway.service;

import com.platform.gateway.dto.request.AuditQueryRequest;
import com.platform.gateway.dto.response.AuditEventResponse;
import com.platform.gateway.dto.response.AuditStatsResponse;
import com.platform.gateway.dto.response.PageResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;

/**
 * 审计服务
 * MVP 阶段返回模拟数据
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditService {

    /**
     * 查询审计事件列表
     */
    public PageResponse<AuditEventResponse> getEvents(String tenantId, AuditQueryRequest request) {
        log.debug("Query audit events: tenant={}, request={}", tenantId, request);

        // MVP: 返回模拟数据
        List<AuditEventResponse> events = generateMockEvents(tenantId, request);

        int total = events.size();
        int totalPages = (int) Math.ceil((double) total / request.getPageSize());

        return PageResponse.<AuditEventResponse>builder()
                .items(events)
                .totalCount((long) total)
                .pageNumber(request.getPageNumber())
                .totalPages(totalPages)
                .hasNext(request.getPageNumber() < totalPages)
                .build();
    }

    /**
     * 获取单个审计事件
     */
    public AuditEventResponse getEvent(String tenantId, Long eventId) {
        log.debug("Get audit event: tenant={}, eventId={}", tenantId, eventId);

        // MVP: 返回模拟数据
        return AuditEventResponse.builder()
                .id(eventId)
                .eventId("evt_" + eventId)
                .eventType("user.login")
                .eventCategory("security")
                .severity("info")
                .tenantId(tenantId)
                .userId("user_001")
                .action("login")
                .requestId("req_" + UUID.randomUUID().toString().substring(0, 8))
                .traceId("trace_" + UUID.randomUUID().toString().substring(0, 8))
                .ipAddress("192.168.1.100")
                .sourceService("gateway-java")
                .createdAt(Instant.now())
                .build();
    }

    /**
     * 获取事件类型列表
     */
    public List<String> getEventTypes() {
        return Arrays.asList(
                "user.login",
                "user.logout",
                "user.password_reset",
                "session.created",
                "session.deleted",
                "tool.executed",
                "approval.approved",
                "approval.rejected",
                "agent.run_started",
                "agent.run_completed"
        );
    }

    /**
     * 获取审计统计
     */
    public AuditStatsResponse getStats(String tenantId, Instant startTime, Instant endTime) {
        log.debug("Get audit stats: tenant={}, start={}, end={}", tenantId, startTime, endTime);

        return AuditStatsResponse.builder()
                .totalEvents(1250L)
                .bySeverity(Map.of(
                        "info", 1000L,
                        "warn", 150L,
                        "error", 80L,
                        "critical", 20L
                ))
                .byCategory(Map.of(
                        "lifecycle", 500L,
                        "security", 300L,
                        "business", 350L,
                        "system", 100L
                ))
                .byEventType(Map.of(
                        "user.login", 200L,
                        "tool.executed", 400L,
                        "agent.run_completed", 350L
                ))
                .build();
    }

    /**
     * 导出审计数据
     */
    public byte[] exportEvents(String tenantId, AuditQueryRequest request, String format) {
        log.info("Export audit events: tenant={}, format={}", tenantId, format);

        // MVP: 返回模拟 CSV 数据
        StringBuilder sb = new StringBuilder();
        sb.append("event_id,event_type,severity,user_id,created_at\n");
        sb.append("evt_001,user.login,info,user_001,2026-05-09T10:00:00Z\n");
        sb.append("evt_002,tool.executed,info,user_001,2026-05-09T10:01:00Z\n");

        return sb.toString().getBytes();
    }

    private List<AuditEventResponse> generateMockEvents(String tenantId, AuditQueryRequest request) {
        List<AuditEventResponse> events = new ArrayList<>();
        String[] eventTypes = {"user.login", "tool.executed", "agent.run_completed", "approval.approved"};
        String[] categories = {"security", "business", "lifecycle"};
        String[] severities = {"info", "warn", "error"};

        Random random = new Random();
        int count = Math.min(request.getPageSize(), 20);

        for (int i = 0; i < count; i++) {
            events.add(AuditEventResponse.builder()
                    .id((long) (request.getPageNumber() - 1) * request.getPageSize() + i + 1)
                    .eventId("evt_" + UUID.randomUUID().toString().substring(0, 8))
                    .eventType(eventTypes[random.nextInt(eventTypes.length)])
                    .eventCategory(categories[random.nextInt(categories.length)])
                    .severity(severities[random.nextInt(severities.length)])
                    .tenantId(tenantId)
                    .userId("user_" + (random.nextInt(10) + 1))
                    .action("execute")
                    .requestId("req_" + UUID.randomUUID().toString().substring(0, 8))
                    .sourceService("gateway-java")
                    .createdAt(Instant.now().minusSeconds(random.nextInt(86400)))
                    .build());
        }

        return events;
    }
}
