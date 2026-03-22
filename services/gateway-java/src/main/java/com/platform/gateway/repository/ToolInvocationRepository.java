package com.platform.gateway.repository;

import com.platform.gateway.entity.ToolInvocation;
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
 * 工具调用明细 Repository
 */
@Repository
public interface ToolInvocationRepository extends JpaRepository<ToolInvocation, UUID> {

    /**
     * 按运行ID查询
     */
    List<ToolInvocation> findByRunId(UUID runId);

    /**
     * 按运行ID查询（分页）
     */
    Page<ToolInvocation> findByRunId(UUID runId, Pageable pageable);

    /**
     * 按工具名称查询
     */
    List<ToolInvocation> findByToolName(String toolName);

    /**
     * 按工具名称和时间范围查询
     */
    @Query("SELECT t FROM ToolInvocation t WHERE t.toolName = :toolName " +
           "AND t.createdAt >= :startTime AND t.createdAt < :endTime")
    List<ToolInvocation> findByToolNameAndCreatedAtBetween(
            @Param("toolName") String toolName,
            @Param("startTime") Instant startTime,
            @Param("endTime") Instant endTime);

    /**
     * 按状态统计
     */
    long countByStatus(String status);

    /**
     * 按状态和工具名称统计
     */
    long countByStatusAndToolName(String status, String toolName);

    /**
     * 按风险等级查询
     */
    @Query("SELECT t FROM ToolInvocation t WHERE t.riskLevel IN :riskLevels")
    List<ToolInvocation> findByRiskLevel(@Param("riskLevels") List<String> riskLevels);

    /**
     * 按审批ID查询
     */
    Optional<ToolInvocation> findByApprovalId(UUID approvalId);

    /**
     * 按ID和运行ID查询
     */
    Optional<ToolInvocation> findByIdAndRunId(UUID id, UUID runId);

    /**
     * 统计工具调用次数
     */
    @Query("SELECT COUNT(t) FROM ToolInvocation t WHERE t.toolName = :toolName")
    long countByToolName(@Param("toolName") String toolName);

    /**
     * 统计工具成功次数
     */
    @Query("SELECT COUNT(t) FROM ToolInvocation t WHERE t.toolName = :toolName AND t.status = 'success'")
    long countSuccessByToolName(@Param("toolName") String toolName);
}
