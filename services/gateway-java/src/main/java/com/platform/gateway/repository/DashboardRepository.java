package com.platform.gateway.repository;

import com.platform.gateway.dto.response.DailyCostStatsResponse;
import com.platform.gateway.dto.response.DailyRunStatsResponse;
import com.platform.gateway.dto.response.ModelCallStatsResponse;
import com.platform.gateway.dto.response.TokenDistributionResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * 仪表盘数据仓库
 * 使用原生 SQL 进行聚合查询
 */
@Slf4j
@Repository
@RequiredArgsConstructor
public class DashboardRepository {

    private final JdbcTemplate jdbcTemplate;

    /**
     * 获取仪表盘统计数据
     */
    public DashboardStats getStats(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                COUNT(DISTINCT s.id) as total_sessions,
                COUNT(r.id) as total_runs,
                COALESCE(SUM(r.total_tokens), 0) as total_tokens,
                COALESCE(SUM(r.total_cost_usd), 0) as total_cost,
                CASE WHEN COUNT(r.id) > 0
                    THEN ROUND(100.0 * SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) / COUNT(r.id), 2)
                    ELSE 100.0 END as success_rate,
                CASE WHEN COUNT(r.id) > 0
                    THEN ROUND(AVG(r.duration_ms)::numeric, 0)
                    ELSE 0 END as avg_response_time,
                COUNT(DISTINCT r.user_id) as active_users,
                (SELECT COUNT(*) FROM approval_task
                 WHERE tenant_id = ? AND status = 'pending' AND expires_at > NOW()) as pending_approvals
            FROM agent_session s
            LEFT JOIN agent_run r ON s.id = r.session_id
            WHERE s.tenant_id = ?
              AND s.created_at >= ?
              AND s.created_at < ?
            """;

        return jdbcTemplate.queryForObject(sql, (rs, rowNum) -> DashboardStats.builder()
                .totalSessions(rs.getLong("total_sessions"))
                .totalRuns(rs.getLong("total_runs"))
                .totalTokens(rs.getLong("total_tokens"))
                .totalCostUsd(rs.getDouble("total_cost"))
                .successRate(rs.getDouble("success_rate"))
                .avgResponseTimeMs(rs.getDouble("avg_response_time"))
                .activeUsers(rs.getLong("active_users"))
                .pendingApprovals(rs.getLong("pending_approvals"))
                .build(),
                tenantId, tenantId, startDate.atStartOfDay(), endDate.plusDays(1).atStartOfDay());
    }

    /**
     * 获取每日运行统计
     */
    public List<DailyRunStatsResponse> getDailyRunStats(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                DATE(r.started_at) as date,
                COUNT(*) as runs,
                SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END) as failed,
                ROUND(AVG(r.duration_ms)::numeric, 0) as avg_duration
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND r.started_at >= ?
              AND r.started_at < ?
            GROUP BY DATE(r.started_at)
            ORDER BY DATE(r.started_at)
            """;

        return jdbcTemplate.query(sql, (rs, rowNum) -> DailyRunStatsResponse.builder()
                        .date(rs.getDate("date").toLocalDate().format(DateTimeFormatter.ISO_LOCAL_DATE))
                        .runs(rs.getLong("runs"))
                        .successful(rs.getLong("successful"))
                        .failed(rs.getLong("failed"))
                        .avgDurationMs(rs.getDouble("avg_duration"))
                        .build(),
                tenantId, startDate.atStartOfDay(), endDate.plusDays(1).atStartOfDay());
    }

    /**
     * 获取每日成本统计
     */
    public List<DailyCostStatsResponse> getDailyCostStats(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                DATE(r.started_at) as date,
                COALESCE(SUM(r.total_cost_usd), 0) as cost_usd,
                COALESCE(SUM(r.total_tokens), 0) as tokens
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND r.started_at >= ?
              AND r.started_at < ?
            GROUP BY DATE(r.started_at)
            ORDER BY DATE(r.started_at)
            """;

        return jdbcTemplate.query(sql, (rs, rowNum) -> DailyCostStatsResponse.builder()
                        .date(rs.getDate("date").toLocalDate().format(DateTimeFormatter.ISO_LOCAL_DATE))
                        .costUsd(rs.getDouble("cost_usd"))
                        .tokens(rs.getLong("tokens"))
                        .build(),
                tenantId, startDate.atStartOfDay(), endDate.plusDays(1).atStartOfDay());
    }

    /**
     * 获取 Token 分布
     */
    public List<TokenDistributionResponse> getTokenDistribution(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                r.model_used as model,
                SUM(r.total_tokens) as tokens,
                SUM(r.total_cost_usd) as cost_usd
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND r.started_at >= ?
              AND r.started_at < ?
              AND r.model_used IS NOT NULL
            GROUP BY r.model_used
            ORDER BY tokens DESC
            """;

        List<TokenDistributionResponse> results = jdbcTemplate.query(sql, (rs, rowNum) -> TokenDistributionResponse.builder()
                        .model(rs.getString("model"))
                        .tokens(rs.getLong("tokens"))
                        .costUsd(rs.getDouble("cost_usd"))
                        .percentage(0.0) // 稍后计算
                        .build(),
                tenantId, startDate.atStartOfDay(), endDate.plusDays(1).atStartOfDay());

        // 计算百分比
        long totalTokens = results.stream().mapToLong(TokenDistributionResponse::getTokens).sum();
        if (totalTokens > 0) {
            results.forEach(r -> r.setPercentage(Math.round(r.getTokens() * 1000.0 / totalTokens) / 10.0));
        }

        return results;
    }

    /**
     * 获取模型调用统计
     */
    public List<ModelCallStatsResponse> getModelCallStats(String tenantId, LocalDate startDate, LocalDate endDate) {
        String sql = """
            SELECT
                r.model_used as model,
                COUNT(*) as total_calls,
                ROUND(100.0 * SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
                ROUND(AVG(r.duration_ms)::numeric, 0) as avg_latency,
                SUM(r.total_tokens) as total_tokens,
                SUM(r.total_cost_usd) as cost_usd
            FROM agent_run r
            WHERE r.tenant_id = ?
              AND r.started_at >= ?
              AND r.started_at < ?
              AND r.model_used IS NOT NULL
            GROUP BY r.model_used
            ORDER BY total_calls DESC
            """;

        return jdbcTemplate.query(sql, (rs, rowNum) -> ModelCallStatsResponse.builder()
                        .model(rs.getString("model"))
                        .totalCalls(rs.getLong("total_calls"))
                        .successRate(rs.getDouble("success_rate"))
                        .avgLatencyMs(rs.getDouble("avg_latency"))
                        .totalTokens(rs.getLong("total_tokens"))
                        .costUsd(rs.getDouble("cost_usd"))
                        .build(),
                tenantId, startDate.atStartOfDay(), endDate.plusDays(1).atStartOfDay());
    }

    /**
     * 仪表盘统计数据内部类
     */
    @lombok.Data
    @lombok.Builder
    public static class DashboardStats {
        private Long totalSessions;
        private Long totalRuns;
        private Long totalTokens;
        private Double totalCostUsd;
        private Double successRate;
        private Double avgResponseTimeMs;
        private Long activeUsers;
        private Long pendingApprovals;
    }
}
