package com.platform.gateway.repository;

import lombok.Builder;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;

/**
 * 租户配额数据仓库
 *
 * <p>使用 JdbcTemplate 原生 SQL 聚合 agent_run 表数据，
 * 提供配额使用情况和用量统计查询。
 *
 * <p>【性能优化】
 * <ul>
 *   <li>所有查询都使用 (tenant_id, started_at) 复合索引</li>
 *   <li>聚合查询使用 COALESCE 避免 NULL 结果</li>
 *   <li>配合 Redis 缓存降低数据库压力</li>
 * </ul>
 *
 * @see com.platform.gateway.service.TenantService
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class TenantQuotaRepository {

    private final JdbcTemplate jdbcTemplate;

    /**
     * 获取指定日期的 Token 使用量
     */
    public Long getDailyTokenUsage(String tenantId, LocalDate date) {
        String sql = """
            SELECT COALESCE(SUM(r.total_tokens), 0)
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND DATE(r.started_at) = ?
            """;

        Long result = jdbcTemplate.queryForObject(sql, Long.class, tenantId, date);
        return result != null ? result : 0L;
    }

    /**
     * 获取当月成本使用量
     */
    public Double getMonthlyCostUsage(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT COALESCE(SUM(r.total_cost_usd), 0)
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND DATE(r.started_at) >= ?
              AND DATE(r.started_at) <= ?
            """;

        Double result = jdbcTemplate.queryForObject(sql, Double.class, tenantId, startDate, endDate);
        return result != null ? result : 0.0;
    }

    /**
     * 获取当月 Token 使用量
     */
    public Long getMonthlyTokenUsage(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT COALESCE(SUM(r.total_tokens), 0)
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND DATE(r.started_at) >= ?
              AND DATE(r.started_at) <= ?
            """;

        Long result = jdbcTemplate.queryForObject(sql, Long.class, tenantId, startDate, endDate);
        return result != null ? result : 0L;
    }

    /**
     * 获取活跃会话数
     */
    public Long getActiveSessionCount(String tenantId) {
        String sql = """
            SELECT COUNT(*)
            FROM agent_session
            WHERE tenant_id = ?
              AND status = 'active'
            """;

        Long result = jdbcTemplate.queryForObject(sql, Long.class, tenantId);
        return result != null ? result : 0L;
    }

    /**
     * 获取活跃运行数
     */
    public Long getActiveRunCount(String tenantId) {
        String sql = """
            SELECT COUNT(*)
            FROM agent_run r
            JOIN agent_session s ON r.session_id = s.id
            WHERE r.tenant_id = ?
              AND r.status = 'running'
            """;

        Long result = jdbcTemplate.queryForObject(sql, Long.class, tenantId);
        return result != null ? result : 0L;
    }

    /**
     * 获取模型维度统计
     */
    public List<ModelUsageStats> getModelStats(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                r.model_used as model,
                COUNT(*) as total_calls,
                SUM(r.total_tokens) as total_tokens,
                COALESCE(SUM(r.total_cost_usd), 0) as total_cost,
                ROUND(AVG(r.duration_ms)::numeric, 0) as avg_latency_ms
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND DATE(r.started_at) >= ?
              AND DATE(r.started_at) <= ?
              AND r.model_used IS NOT NULL
            GROUP BY r.model_used
            ORDER BY total_calls DESC
            """;

        return jdbcTemplate.query(sql, (rs, rowNum) -> ModelUsageStats.builder()
                .model(rs.getString("model"))
                .totalCalls(rs.getLong("total_calls"))
                .totalTokens(rs.getLong("total_tokens"))
                .totalCost(rs.getDouble("total_cost"))
                .avgLatencyMs(rs.getLong("avg_latency_ms"))
                .build(),
                tenantId, startDate, endDate);
    }

    /**
     * 获取请求统计
     */
    public RequestUsageStats getRequestStats(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                COUNT(*) as total_requests,
                SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as successful_requests,
                SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failed_requests,
                CASE WHEN COUNT(*) > 0
                    THEN ROUND(100.0 * SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2)
                    ELSE 100.0 END as success_rate,
                CASE WHEN COUNT(*) > 0
                    THEN ROUND(AVG(r.duration_ms)::numeric, 1)
                    ELSE 0 END as avg_response_time_ms
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND DATE(r.started_at) >= ?
              AND DATE(r.started_at) <= ?
            """;

        return jdbcTemplate.queryForObject(sql, (rs, rowNum) -> RequestUsageStats.builder()
                .totalRequests(rs.getLong("total_requests"))
                .successfulRequests(rs.getLong("successful_requests"))
                .failedRequests(rs.getLong("failed_requests"))
                .successRate(rs.getDouble("success_rate"))
                .avgResponseTimeMs(rs.getDouble("avg_response_time_ms"))
                .build(),
                tenantId, startDate, endDate);
    }

    /**
     * 获取 Token 统计（输入/输出/总量/日均）
     */
    public TokenUsageStats getTokenStats(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                COALESCE(SUM(r.total_tokens), 0) as total_tokens,
                COUNT(*) as day_count
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND DATE(r.started_at) >= ?
              AND DATE(r.started_at) <= ?
            """;

        return jdbcTemplate.queryForObject(sql, (rs, rowNum) -> {
            long totalTokens = rs.getLong("total_tokens");
            long dayCount = rs.getLong("day_count");
            // 日均：如果有数据则除以实际天数跨度，否则为0
            long days = Math.max(1, java.time.temporal.ChronoUnit.DAYS.between(startDate, endDate) + 1);
            long dailyAverage = dayCount > 0 ? totalTokens / days : 0L;

            return TokenUsageStats.builder()
                    .totalTokens(totalTokens)
                    .dailyAverage(dailyAverage)
                    .build();
        }, tenantId, startDate, endDate);
    }

    // ==================== 内部 DTO ====================

    /**
     * 模型使用统计
     */
    @Data
    @Builder
    public static class ModelUsageStats {
        private String model;
        private Long totalCalls;
        private Long totalTokens;
        private Double totalCost;
        private Long avgLatencyMs;
    }

    /**
     * 请求使用统计
     */
    @Data
    @Builder
    public static class RequestUsageStats {
        private Long totalRequests;
        private Long successfulRequests;
        private Long failedRequests;
        private Double successRate;
        private Double avgResponseTimeMs;
    }

    /**
     * Token 使用统计
     */
    @Data
    @Builder
    public static class TokenUsageStats {
        private Long totalTokens;
        private Long dailyAverage;
    }
}
