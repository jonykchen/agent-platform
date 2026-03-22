package com.platform.gateway.repository;

import com.platform.gateway.entity.AgentSession;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * 会话仓库
 */
@Repository
public interface AgentSessionRepository extends JpaRepository<AgentSession, UUID> {

    /**
     * 按租户和用户查询所有会话
     */
    List<AgentSession> findByTenantIdAndUserId(String tenantId, String userId);

    /**
     * 按租户、用户和状态查询会话（分页）
     */
    Page<AgentSession> findByTenantIdAndUserIdAndStatus(
            String tenantId, String userId, String status, Pageable pageable);

    /**
     * 按租户和用户查询会话（分页）
     */
    Page<AgentSession> findByTenantIdAndUserId(String tenantId, String userId, Pageable pageable);

    /**
     * 按租户、用户和ID查询会话
     */
    Optional<AgentSession> findByIdAndTenantIdAndUserId(UUID id, String tenantId, String userId);

    /**
     * 按租户、用户查询，标题模糊搜索（分页）
     */
    @Query("SELECT s FROM AgentSession s WHERE s.tenantId = :tenantId AND s.userId = :userId " +
           "AND (:status IS NULL OR s.status = :status) " +
           "AND (:search IS NULL OR LOWER(s.title) LIKE LOWER(CONCAT('%', :search, '%')))")
    Page<AgentSession> findByTenantAndUserWithFilter(
            @Param("tenantId") String tenantId,
            @Param("userId") String userId,
            @Param("status") String status,
            @Param("search") String search,
            Pageable pageable);

    /**
     * 统计用户的活跃会话数
     */
    long countByTenantIdAndUserIdAndStatus(String tenantId, String userId, String status);
}