package com.platform.gateway.repository;

import com.platform.gateway.entity.UsageLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

/**
 * 用量日志 Repository
 */
@Repository
public interface UsageLogRepository extends JpaRepository<UsageLog, UUID> {

    /**
     * 聚合指定日期的 Token 使用量
     */
    @Query("SELECT COALESCE(SUM(u.totalTokens), 0) FROM UsageLog u " +
           "WHERE u.tenantId = :tenantId AND u.logDate = :date")
    Long sumTokensByDate(@Param("tenantId") String tenantId, @Param("date") LocalDate date);

    /**
     * 聚合指定月份范围的 Token 使用量
     */
    @Query("SELECT COALESCE(SUM(u.totalTokens), 0) FROM UsageLog u " +
           "WHERE u.tenantId = :tenantId AND u.logDate >= :startDate AND u.logDate <= :endDate")
    Long sumTokensByMonth(@Param("tenantId") String tenantId,
                          @Param("startDate") LocalDate startDate,
                          @Param("endDate") LocalDate endDate);

    /**
     * 聚合指定月份范围的成本
     */
    @Query("SELECT COALESCE(SUM(u.costUsd), 0) FROM UsageLog u " +
           "WHERE u.tenantId = :tenantId AND u.logDate >= :startDate AND u.logDate <= :endDate")
    Double sumCostByMonth(@Param("tenantId") String tenantId,
                          @Param("startDate") LocalDate startDate,
                          @Param("endDate") LocalDate endDate);
}
