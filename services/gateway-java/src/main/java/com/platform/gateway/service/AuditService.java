package com.platform.gateway.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.platform.gateway.dto.request.AuditQueryRequest;
import com.platform.gateway.dto.response.AuditEventResponse;
import com.platform.gateway.dto.response.AuditStatsResponse;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.entity.AuditEvent;
import com.platform.gateway.repository.AuditEventRepository;
import jakarta.persistence.criteria.Predicate;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

/**
 * 审计服务
 * 提供审计事件的查询和记录功能
 *
 * 安全特性：
 * - 查询只返回当前租户的数据（自动过滤 tenant_id）
 * - 写入使用 native INSERT 避免触发 UPDATE
 * - 审计表不可删改（由数据库触发器保证）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AuditService {

    private final AuditEventRepository auditEventRepository;
    private final ObjectMapper objectMapper;

    /**
     * 查询审计事件列表
     */
    public PageResponse<AuditEventResponse> getEvents(String tenantId, AuditQueryRequest request) {
        log.debug("Query audit events: tenant={}, request={}", tenantId, request);

        // 构建动态查询条件
        Specification<AuditEvent> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            // 强制租户隔离
            predicates.add(cb.equal(root.get("tenantId"), tenantId));

            // 可选条件
            if (request.getEventType() != null) {
                predicates.add(cb.equal(root.get("eventType"), request.getEventType()));
            }
            if (request.getEventCategory() != null) {
                predicates.add(cb.equal(root.get("eventCategory"), request.getEventCategory()));
            }
            if (request.getSeverity() != null) {
                predicates.add(cb.equal(root.get("severity"), request.getSeverity()));
            }
            if (request.getUserId() != null) {
                predicates.add(cb.equal(root.get("userId"), request.getUserId()));
            }
            if (request.getResourceType() != null) {
                predicates.add(cb.equal(root.get("resourceType"), request.getResourceType()));
            }
            if (request.getResourceId() != null) {
                predicates.add(cb.equal(root.get("resourceId"), request.getResourceId()));
            }
            if (request.getStartTime() != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("createdAt"), request.getStartTime()));
            }
            if (request.getEndTime() != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("createdAt"), request.getEndTime()));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };

        // 分页和排序
        Sort sort = request.getSortDescending()
            ? Sort.by(Sort.Direction.DESC, request.getSortBy() != null ? request.getSortBy() : "createdAt")
            : Sort.by(Sort.Direction.ASC, request.getSortBy() != null ? request.getSortBy() : "createdAt");
        Pageable pageable = PageRequest.of(request.getPageNumber() - 1, request.getPageSize(), sort);

        // 查询
        Page<AuditEvent> page = auditEventRepository.findAll(spec, pageable);

        // 转换响应
        List<AuditEventResponse> items = page.getContent().stream()
            .map(this::toResponse)
            .collect(Collectors.toList());

        return PageResponse.<AuditEventResponse>builder()
            .items(items)
            .totalCount(page.getTotalElements())
            .pageNumber(request.getPageNumber())
            .totalPages(page.getTotalPages())
            .hasNext(page.hasNext())
            .build();
    }

    /**
     * 获取单个审计事件
     */
    public AuditEventResponse getEvent(String tenantId, Long eventId) {
        AuditEvent event = auditEventRepository.findById(eventId)
            .orElseThrow(() -> new IllegalArgumentException("Audit event not found: " + eventId));

        // 验证租户归属
        if (!tenantId.equals(event.getTenantId())) {
            throw new IllegalArgumentException("Audit event not found: " + eventId);
        }

        return toResponse(event);
    }

    /**
     * 获取事件类型列表
     */
    public List<String> getEventTypes() {
        return Arrays.asList(
            "user.login",
            "user.logout",
            "user.password_reset",
            "user.role_changed",
            "session.created",
            "session.deleted",
            "tool.executed",
            "tool.approved",
            "tool.rejected",
            "agent.run_started",
            "agent.run_completed",
            "agent.run_failed",
            "api_key.created",
            "api_key.revoked",
            "tenant.config_changed",
            "security.alert"
        );
    }

    /**
     * 获取审计统计
     */
    public AuditStatsResponse getStats(String tenantId, Instant startTime, Instant endTime) {
        log.debug("Get audit stats: tenant={}, start={}, end={}", tenantId, startTime, endTime);

        // 总数
        long totalEvents = auditEventRepository.countByTenantIdAndTimeRange(tenantId, startTime, endTime);

        // 按严重程度分组
        Map<String, Long> bySeverity = new HashMap<>();
        for (Object[] row : auditEventRepository.countBySeverity(tenantId, startTime, endTime)) {
            bySeverity.put((String) row[0], (Long) row[1]);
        }

        // 按事件类别分组
        Map<String, Long> byCategory = new HashMap<>();
        for (Object[] row : auditEventRepository.countByCategory(tenantId, startTime, endTime)) {
            byCategory.put((String) row[0], (Long) row[1]);
        }

        // 按事件类型分组（Top 10）
        Map<String, Long> byEventType = new LinkedHashMap<>();
        int count = 0;
        for (Object[] row : auditEventRepository.countByEventTypeTop(tenantId, startTime, endTime)) {
            byEventType.put((String) row[0], (Long) row[1]);
            if (++count >= 10) break;
        }

        return AuditStatsResponse.builder()
            .totalEvents(totalEvents)
            .bySeverity(bySeverity)
            .byCategory(byCategory)
            .byEventType(byEventType)
            .build();
    }

    /**
     * 导出审计数据
     */
    public byte[] exportEvents(String tenantId, AuditQueryRequest request, String format) {
        log.info("Export audit events: tenant={}, format={}", tenantId, format);

        // 查询所有匹配的事件（不分页）
        Specification<AuditEvent> spec = (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();
            predicates.add(cb.equal(root.get("tenantId"), tenantId));

            if (request.getStartTime() != null) {
                predicates.add(cb.greaterThanOrEqualTo(root.get("createdAt"), request.getStartTime()));
            }
            if (request.getEndTime() != null) {
                predicates.add(cb.lessThanOrEqualTo(root.get("createdAt"), request.getEndTime()));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };

        List<AuditEvent> events = auditEventRepository.findAll(spec, Sort.by(Sort.Direction.DESC, "createdAt"));

        if ("csv".equalsIgnoreCase(format)) {
            return exportToCsv(events);
        } else {
            return exportToJson(events);
        }
    }

    /**
     * 异步记录审计事件
     */
    @Async
    @Transactional
    public void recordEvent(AuditEvent event) {
        try {
            String beforeState = event.getBeforeState() != null ? toJson(event.getBeforeState()) : null;
            String afterState = event.getAfterState() != null ? toJson(event.getAfterState()) : null;
            String details = event.getDetails() != null ? toJson(event.getDetails()) : "{}";

            auditEventRepository.insertNative(
                event.getEventId(),
                event.getEventType(),
                event.getEventCategory(),
                event.getSeverity(),
                event.getTenantId(),
                event.getUserId(),
                event.getResourceType(),
                event.getResourceId(),
                event.getAction(),
                beforeState != null ? beforeState : "{}",
                afterState != null ? afterState : "{}",
                details,
                event.getRequestId(),
                event.getTraceId(),
                event.getIpAddress(),
                event.getUserAgent(),
                event.getSourceService() != null ? event.getSourceService() : "gateway-java",
                event.getCreatedAt() != null ? event.getCreatedAt() : Instant.now()
            );

            log.debug("Audit event recorded: type={}, tenant={}, user={}",
                event.getEventType(), event.getTenantId(), event.getUserId());

        } catch (Exception e) {
            log.error("Failed to record audit event: {}", e.getMessage(), e);
            // 不抛异常，避免影响主流程
        }
    }

    /**
     * 创建审计事件构建器
     */
    public static AuditEventBuilder builder(String tenantId, String userId) {
        return new AuditEventBuilder(tenantId, userId);
    }

    // ========== 辅助方法 ==========

    private AuditEventResponse toResponse(AuditEvent event) {
        return AuditEventResponse.builder()
            .id(event.getId())
            .eventId(event.getEventId())
            .eventType(event.getEventType())
            .eventCategory(event.getEventCategory())
            .severity(event.getSeverity())
            .tenantId(event.getTenantId())
            .userId(event.getUserId())
            .resourceType(event.getResourceType())
            .resourceId(event.getResourceId())
            .action(event.getAction())
            .beforeState(event.getBeforeState())
            .afterState(event.getAfterState())
            .details(event.getDetails())
            .requestId(event.getRequestId())
            .traceId(event.getTraceId())
            .ipAddress(event.getIpAddress())
            .userAgent(event.getUserAgent())
            .sourceService(event.getSourceService())
            .createdAt(event.getCreatedAt())
            .build();
    }

    private byte[] exportToCsv(List<AuditEvent> events) {
        StringBuilder sb = new StringBuilder();
        sb.append("event_id,event_type,event_category,severity,user_id,action,created_at\n");
        for (AuditEvent e : events) {
            sb.append(String.format("%s,%s,%s,%s,%s,%s,%s\n",
                e.getEventId(),
                e.getEventType(),
                e.getEventCategory(),
                e.getSeverity(),
                e.getUserId(),
                e.getAction(),
                e.getCreatedAt()
            ));
        }
        return sb.toString().getBytes();
    }

    private byte[] exportToJson(List<AuditEvent> events) {
        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(
                events.stream().map(this::toResponse).collect(Collectors.toList())
            );
        } catch (JsonProcessingException e) {
            throw new RuntimeException("Failed to export JSON", e);
        }
    }

    private String toJson(Map<String, Object> map) {
        try {
            return objectMapper.writeValueAsString(map);
        } catch (JsonProcessingException e) {
            return "{}";
        }
    }

    /**
     * 审计事件构建器（流式 API）
     */
    public static class AuditEventBuilder {
        private final AuditEvent event;

        public AuditEventBuilder(String tenantId, String userId) {
            this.event = new AuditEvent();
            event.setTenantId(tenantId);
            event.setUserId(userId);
            event.setCreatedAt(Instant.now());
            event.setEventId("evt_" + UUID.randomUUID().toString().substring(0, 8));
        }

        public AuditEventBuilder type(String eventType, String eventCategory) {
            event.setEventType(eventType);
            event.setEventCategory(eventCategory);
            return this;
        }

        public AuditEventBuilder severity(String severity) {
            event.setSeverity(severity);
            return this;
        }

        public AuditEventBuilder action(String action) {
            event.setAction(action);
            return this;
        }

        public AuditEventBuilder resource(String type, String id) {
            event.setResourceType(type);
            event.setResourceId(id);
            return this;
        }

        public AuditEventBuilder beforeState(Map<String, Object> state) {
            event.setBeforeState(state);
            return this;
        }

        public AuditEventBuilder afterState(Map<String, Object> state) {
            event.setAfterState(state);
            return this;
        }

        public AuditEventBuilder details(Map<String, Object> details) {
            event.setDetails(details);
            return this;
        }

        public AuditEventBuilder requestContext(String requestId, String traceId) {
            event.setRequestId(requestId);
            event.setTraceId(traceId);
            return this;
        }

        public AuditEventBuilder source(String ip, String userAgent, String service) {
            event.setIpAddress(ip);
            event.setUserAgent(userAgent);
            event.setSourceService(service);
            return this;
        }

        public AuditEvent build() {
            if (event.getAction() == null) {
                event.setAction(event.getEventType());
            }
            return event;
        }
    }
}