package com.platform.gateway.repository;

import com.platform.gateway.entity.ApprovalTask;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 审批任务 Repository
 */
@Repository
public interface ApprovalTaskRepository extends JpaRepository<ApprovalTask, UUID> {

    /**
     * 按租户查询审批任务（分页）
     */
    Page<ApprovalTask> findByTenantId(String tenantId, Pageable pageable);

    /**
     * 按租户和状态查询
     */
    Page<ApprovalTask> findByTenantIdAndStatus(String tenantId, String status, Pageable pageable);

    /**
     * 按ID和租户查询
     */
    Optional<ApprovalTask> findByIdAndTenantId(UUID id, String tenantId);

    /**
     * 按受理人和状态查询（待处理审批）
     */
    List<ApprovalTask> findByAssigneeIdAndStatus(String assigneeId, String status);

    /**
     * 按请求人查询
     */
    Page<ApprovalTask> findByRequesterId(String requesterId, Pageable pageable);

    /**
     * 复杂查询：按条件筛选审批任务
     */
    @Query("SELECT a FROM ApprovalTask a WHERE a.tenantId = :tenantId " +
           "AND (:status IS NULL OR a.status = :status) " +
           "AND (:priority IS NULL OR a.priority = :priority) " +
           "AND (:taskType IS NULL OR a.taskType = :taskType) " +
           "AND (:assigneeId IS NULL OR a.assigneeId = :assigneeId)")
    Page<ApprovalTask> findByConditions(
        @Param("tenantId") String tenantId,
        @Param("status") String status,
        @Param("priority") String priority,
        @Param("taskType") String taskType,
        @Param("assigneeId") String assigneeId,
        Pageable pageable
    );

    /**
     * 查询过期的待处理审批
     */
    @Query("SELECT a FROM ApprovalTask a WHERE a.status = 'pending' AND a.expiresAt < :now")
    List<ApprovalTask> findExpiredPendingApprovals(@Param("now") Instant now);

    /**
     * 统计租户待处理审批数
     */
    long countByTenantIdAndStatus(String tenantId, String status);

    /**
     * 统计用户待处理审批数
     */
    long countByAssigneeIdAndStatus(String assigneeId, String status);

    /**
     * 按请求人查询（按创建时间降序）
     */
    List<ApprovalTask> findByRequesterIdOrderByCreatedAtDesc(String requesterId);

    /**
     * 按过期时间和状态查询（用于定时任务清理过期审批）
     */
    @Query("SELECT a FROM ApprovalTask a WHERE a.expiresAt < :expiresAt AND a.status = :status")
    List<ApprovalTask> findByExpiresAtBeforeAndStatus(
            @Param("expiresAt") Instant expiresAt,
            @Param("status") String status);
}
