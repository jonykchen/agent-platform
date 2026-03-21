package com.platform.governance.approval;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * 审批任务 Repository
 */
@Repository
public interface ApprovalRepository extends JpaRepository<ApprovalTask, String> {

    /**
     * 查询待审批任务
     */
    List<ApprovalTask> findByStatus(String status);

    /**
     * 查询指定审批人的待审批任务
     */
    List<ApprovalTask> findByAssigneeIdAndStatus(String assigneeId, String status);

    /**
     * 查询即将过期的待审批任务
     */
    List<ApprovalTask> findByStatusAndExpiresAtBefore(String status, Instant expiresAt);

    /**
     * 查询指定运行实例的审批任务
     */
    Optional<ApprovalTask> findByRunId(String runId);

    /**
     * 统计各状态的审批任务数量
     */
    long countByStatus(String status);
}