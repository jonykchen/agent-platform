package com.platform.gateway.repository;

import com.platform.gateway.entity.AuditEvent;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * 审计事件 Repository
 *
 * 注意：审计表只允许 INSERT，禁止 UPDATE/DELETE
 * - 使用 native INSERT 而非 JPA save() 避免触发 UPDATE
 * - 查询方法正常使用
 */
@Repository
public interface AuditEventRepository extends JpaRepository<AuditEvent, Long>, JpaSpecificationExecutor<AuditEvent> {

    /**
     * 按租户 ID 分页查询
     */
    Page<AuditEvent> findByTenantId(String tenantId, Pageable pageable);

    /**
     * 按租户 ID 和事件类型查询
     */
    Page<AuditEvent> findByTenantIdAndEventType(String tenantId, String eventType, Pageable pageable);

    /**
     * 按租户 ID 和严重程度查询
     */
    Page<AuditEvent> findByTenantIdAndSeverity(String tenantId, String severity, Pageable pageable);

    /**
     * 按租户 ID 和时间范围查询
     */
    @Query("SELECT a FROM AuditEvent a WHERE a.tenantId = :tenantId " +
           "AND a.createdAt >= :startTime AND a.createdAt <= :endTime")
    Page<AuditEvent> findByTenantIdAndTimeRange(
        @Param("tenantId") String tenantId,
        @Param("startTime") Instant startTime,
        @Param("endTime") Instant endTime,
        Pageable pageable
    );

    /**
     * 按租户 ID 和用户 ID 查询
     */
    Page<AuditEvent> findByTenantIdAndUserId(String tenantId, String userId, Pageable pageable);

    /**
     * 按 request ID 查询（用于追踪）
     */
    List<AuditEvent> findByRequestId(String requestId);

    /**
     * 按 event ID 查询
     */
    Optional<AuditEvent> findByEventId(String eventId);

    /**
     * 统计：按租户 ID 和时间范围内的总数
     */
    @Query("SELECT COUNT(a) FROM AuditEvent a WHERE a.tenantId = :tenantId " +
           "AND a.createdAt >= :startTime AND a.createdAt <= :endTime")
    long countByTenantIdAndTimeRange(
        @Param("tenantId") String tenantId,
        @Param("startTime") Instant startTime,
        @Param("endTime") Instant endTime
    );

    /**
     * 统计：按严重程度分组计数
     */
    @Query("SELECT a.severity, COUNT(a) FROM AuditEvent a WHERE a.tenantId = :tenantId " +
           "AND a.createdAt >= :startTime AND a.createdAt <= :endTime " +
           "GROUP BY a.severity")
    List<Object[]> countBySeverity(
        @Param("tenantId") String tenantId,
        @Param("startTime") Instant startTime,
        @Param("endTime") Instant endTime
    );

    /**
     * 统计：按事件类别分组计数
     */
    @Query("SELECT a.eventCategory, COUNT(a) FROM AuditEvent a WHERE a.tenantId = :tenantId " +
           "AND a.createdAt >= :startTime AND a.createdAt <= :endTime " +
           "GROUP BY a.eventCategory")
    List<Object[]> countByCategory(
        @Param("tenantId") String tenantId,
        @Param("startTime") Instant startTime,
        @Param("endTime") Instant endTime
    );

    /**
     * 统计：按事件类型分组计数（Top N）
     */
    @Query("SELECT a.eventType, COUNT(a) as cnt FROM AuditEvent a WHERE a.tenantId = :tenantId " +
           "AND a.createdAt >= :startTime AND a.createdAt <= :endTime " +
           "GROUP BY a.eventType ORDER BY cnt DESC")
    List<Object[]> countByEventTypeTop(
        @Param("tenantId") String tenantId,
        @Param("startTime") Instant startTime,
        @Param("endTime") Instant endTime
    );

    /**
     * Native INSERT（避免触发 UPDATE）
     * 审计表触发器会阻止 UPDATE，使用 native query 纯 INSERT
     */
    @Query(value = """
        INSERT INTO audit_event (
            event_id, event_type, event_category, severity,
            tenant_id, user_id, resource_type, resource_id,
            action, before_state, after_state, details,
            request_id, trace_id, ip_address, user_agent, source_service, created_at
        ) VALUES (
            :eventId, :eventType, :eventCategory, :severity,
            :tenantId, :userId, :resourceType, :resourceId,
            :action, :beforeState::jsonb, :afterState::jsonb, :details::jsonb,
            :requestId, :traceId, :ipAddress, :userAgent, :sourceService, :createdAt
        )
        """, nativeQuery = true)
    void insertNative(
        @Param("eventId") String eventId,
        @Param("eventType") String eventType,
        @Param("eventCategory") String eventCategory,
        @Param("severity") String severity,
        @Param("tenantId") String tenantId,
        @Param("userId") String userId,
        @Param("resourceType") String resourceType,
        @Param("resourceId") String resourceId,
        @Param("action") String action,
        @Param("beforeState") String beforeState,
        @Param("afterState") String afterState,
        @Param("details") String details,
        @Param("requestId") String requestId,
        @Param("traceId") String traceId,
        @Param("ipAddress") String ipAddress,
        @Param("userAgent") String userAgent,
        @Param("sourceService") String sourceService,
        @Param("createdAt") Instant createdAt
    );
}