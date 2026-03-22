package com.platform.gateway.repository;

import com.platform.gateway.entity.AgentRun;
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
 * Agent 运行实例 Repository
 */
@Repository
public interface AgentRunRepository extends JpaRepository<AgentRun, UUID> {

    /**
     * 按会话ID查询
     */
    List<AgentRun> findBySessionIdOrderByStartedAtDesc(UUID sessionId);

    /**
     * 按会话ID和运行号查询
     */
    Optional<AgentRun> findBySessionIdAndRunNumber(UUID sessionId, Integer runNumber);

    /**
     * 按租户和时间范围查询（分页）
     */
    Page<AgentRun> findByTenantIdAndStartedAtBetween(
            String tenantId,
            Instant startTime,
            Instant endTime,
            Pageable pageable);

    /**
     * 按用户查询
     */
    Page<AgentRun> findByUserIdOrderByStartedAtDesc(String userId, Pageable pageable);

    /**
     * 按状态统计
     */
    long countByTenantIdAndStatus(String tenantId, String status);

    /**
     * 按模型统计
     */
    @Query("SELECT COUNT(r) FROM AgentRun r WHERE r.tenantId = :tenantId AND r.modelUsed = :model")
    long countByTenantIdAndModel(@Param("tenantId") String tenantId, @Param("model") String model);

    /**
     * 按会话统计运行数
     */
    long countBySessionId(UUID sessionId);

    /**
     * 按ID和租户ID查询
     */
    Optional<AgentRun> findByIdAndTenantId(UUID id, String tenantId);

    /**
     * 按租户ID查询（分页）
     */
    Page<AgentRun> findByTenantId(String tenantId, Pageable pageable);

    /**
     * 按租户ID和用户ID查询（分页）
     */
    Page<AgentRun> findByTenantIdAndUserId(String tenantId, String userId, Pageable pageable);
}
