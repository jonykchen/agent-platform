package com.platform.gateway.repository;

import com.platform.gateway.entity.AgentStep;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.UUID;

/**
 * Agent 执行步骤 Repository
 */
@Repository
public interface AgentStepRepository extends JpaRepository<AgentStep, UUID> {

    /**
     * 按运行ID查询，按步骤顺序排序
     */
    List<AgentStep> findByRunIdOrderByStepOrderAsc(UUID runId);

    /**
     * 按运行ID和步骤类型查询
     */
    List<AgentStep> findByRunIdAndStepType(UUID runId, String stepType);

    /**
     * 统计运行步骤数
     */
    long countByRunId(UUID runId);

    /**
     * 按运行ID和步骤顺序查询
     */
    java.util.Optional<AgentStep> findByRunIdAndStepOrder(UUID runId, Integer stepOrder);

    /**
     * 按步骤类型统计
     */
    long countByRunIdAndStepType(UUID runId, String stepType);
}
