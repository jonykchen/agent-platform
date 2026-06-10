package com.platform.gateway.controller;

import com.platform.gateway.dto.request.AuditQueryRequest;
import com.platform.gateway.dto.response.AuditEventResponse;
import com.platform.gateway.dto.response.AuditStatsResponse;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.service.AuditService;
import com.platform.gateway.service.TenantContextService;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;

/**
 * 审计日志控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/audit")
@RequiredArgsConstructor
@PreAuthorize("hasRole('admin')")  // 审计日志查看为管理员专属
public class AuditController {

    private final AuditService auditService;
    private final TenantContextService tenantContextService;

    /**
     * 查询审计事件列表
     */
    @GetMapping("/events")
    public ResponseEntity<PageResponse<AuditEventResponse>> getEvents(@Valid AuditQueryRequest request) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String requestId = tenantContextService.getCurrentRequestId();

        log.info("Get audit events: requestId={}, tenant={}, page={}",
                requestId, tenantId, request.getPageNumber());

        PageResponse<AuditEventResponse> response = auditService.getEvents(tenantId, request);
        return ResponseEntity.ok(response);
    }

    /**
     * 获取单个审计事件
     */
    @GetMapping("/events/{eventId}")
    public ResponseEntity<AuditEventResponse> getEvent(@PathVariable Long eventId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String requestId = tenantContextService.getCurrentRequestId();

        log.info("Get audit event: requestId={}, tenant={}, eventId={}",
                requestId, tenantId, eventId);

        AuditEventResponse response = auditService.getEvent(tenantId, eventId);
        return ResponseEntity.ok(response);
    }

    /**
     * 导出审计数据
     */
    @GetMapping("/events/export")
    public void exportEvents(
            @Valid AuditQueryRequest request,
            @RequestParam(defaultValue = "csv") String format,
            HttpServletResponse response) throws Exception {

        String tenantId = tenantContextService.getCurrentTenantId();
        String requestId = tenantContextService.getCurrentRequestId();

        // 验证 format 参数，防止 CRLF 注入
        String safeFormat = format.replaceAll("[\\r\\n]", "");
        if (!safeFormat.matches("^(csv|json)$")) {
            safeFormat = "csv";
        }

        log.info("Export audit events: requestId={}, tenant={}, format={}",
                requestId, tenantId, safeFormat);

        byte[] data = auditService.exportEvents(tenantId, request, safeFormat);

        response.setContentType(safeFormat.equals("csv")
                ? "text/csv"
                : MediaType.APPLICATION_JSON_VALUE);
        response.setHeader(HttpHeaders.CONTENT_DISPOSITION,
                "attachment; filename=audit-events." + safeFormat);
        response.getOutputStream().write(data);
        response.getOutputStream().flush();
    }

    /**
     * 获取事件类型列表
     */
    @GetMapping("/events/types")
    public ResponseEntity<List<String>> getEventTypes() {
        List<String> types = auditService.getEventTypes();
        return ResponseEntity.ok(types);
    }

    /**
     * 获取审计统计
     */
    @GetMapping("/stats")
    public ResponseEntity<AuditStatsResponse> getStats(
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant startTime,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) Instant endTime) {

        String tenantId = tenantContextService.getCurrentTenantId();
        String requestId = tenantContextService.getCurrentRequestId();

        log.info("Get audit stats: requestId={}, tenant={}, start={}, end={}",
                requestId, tenantId, startTime, endTime);

        AuditStatsResponse response = auditService.getStats(tenantId, startTime, endTime);
        return ResponseEntity.ok(response);
    }
}
