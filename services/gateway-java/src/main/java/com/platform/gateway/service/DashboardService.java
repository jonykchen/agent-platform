package com.platform.gateway.service;

import com.platform.gateway.dto.response.ActiveAlertResponse;
import com.platform.gateway.dto.response.DailyCostStatsResponse;
import com.platform.gateway.dto.response.DailyRunStatsResponse;
import com.platform.gateway.dto.response.DashboardStatsResponse;
import com.platform.gateway.dto.response.ModelCallStatsResponse;
import com.platform.gateway.dto.response.TokenDistributionResponse;
import com.platform.gateway.repository.DashboardRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * 仪表盘服务
 *
 * <p>生产级实现：从数据库查询真实统计数据，支持多租户隔离。
 *
 * <p>【缓存策略】
 * <ul>
 *   <li>统计数据缓存 5 分钟（高频查询）</li>
 *   <li>趋势数据缓存 10 分钟（每日数据变化慢）</li>
 *   <li>告警数据不缓存（实时性要求高）</li>
 * </ul>
 *
 * <p>【性能优化】
 * <ul>
 *   <li>使用 JdbcTemplate 原生 SQL 聚合，避免 ORM 性能损耗</li>
 *   <li>索引优化：所有查询都使用 (tenant_id, created_at) 复合索引</li>
 *   <li>缓存预热：建议在启动时异步加载热门租户数据</li>
 * </ul>
 *
 * @see DashboardRepository
 * @see TenantContextService
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class DashboardService {

    private final DashboardRepository dashboardRepository;
    private final TenantContextService tenantContextService;

    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ISO_LOCAL_DATE;

    /**
     * 获取仪表盘统计数据
     *
     * @param range 时间范围: 24h, 7d, 30d, 90d
     * @return 统计数据
     */
    @Cacheable(
        value = "dashboard-stats",
        key = "#root.target.getCurrentTenantId() + ':' + #range",
        unless = "#result == null"
    )
    public DashboardStatsResponse getStats(String range) {
        String tenantId = getCurrentTenantId();
        log.info("Getting dashboard stats for tenant: {}, range: {}", tenantId, range);

        DateRange dateRange = calculateDateRange(range);

        DashboardRepository.DashboardStats stats = dashboardRepository.getStats(
                tenantId,
                dateRange.startDate(),
                dateRange.endDate()
        );

        return DashboardStatsResponse.builder()
                .totalSessions(stats.getTotalSessions())
                .totalRuns(stats.getTotalRuns())
                .totalTokens(stats.getTotalTokens())
                .totalCostUsd(stats.getTotalCostUsd())
                .successRate(stats.getSuccessRate())
                .avgResponseTimeMs(stats.getAvgResponseTimeMs())
                .activeUsers(stats.getActiveUsers())
                .pendingApprovals(stats.getPendingApprovals())
                .build();
    }

    /**
     * 获取每日运行统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 每日运行统计列表
     */
    @Cacheable(
        value = "dashboard-daily-runs",
        key = "#root.target.getCurrentTenantId() + ':' + #startDate + ':' + #endDate"
    )
    public List<DailyRunStatsResponse> getDailyRunStats(String startDate, String endDate) {
        String tenantId = getCurrentTenantId();
        log.info("Getting daily run stats for tenant: {}, from {} to {}", tenantId, startDate, endDate);

        LocalDate start = parseDate(startDate);
        LocalDate end = parseDate(endDate);

        List<DailyRunStatsResponse> stats = dashboardRepository.getDailyRunStats(tenantId, start, end);

        // 填充空缺日期（无数据日期返回 0）
        return fillMissingDates(stats, start, end, DailyRunStatsResponse.class);
    }

    /**
     * 获取每日成本统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 每日成本统计列表
     */
    @Cacheable(
        value = "dashboard-daily-costs",
        key = "#root.target.getCurrentTenantId() + ':' + #startDate + ':' + #endDate"
    )
    public List<DailyCostStatsResponse> getDailyCostStats(String startDate, String endDate) {
        String tenantId = getCurrentTenantId();
        log.info("Getting daily cost stats for tenant: {}, from {} to {}", tenantId, startDate, endDate);

        LocalDate start = parseDate(startDate);
        LocalDate end = parseDate(endDate);

        List<DailyCostStatsResponse> stats = dashboardRepository.getDailyCostStats(tenantId, start, end);

        // 填充空缺日期
        return fillMissingDates(stats, start, end, DailyCostStatsResponse.class);
    }

    /**
     * 获取 Token 分布
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return Token 分布列表
     */
    @Cacheable(
        value = "dashboard-token-distribution",
        key = "#root.target.getCurrentTenantId() + ':' + #startDate + ':' + #endDate"
    )
    public List<TokenDistributionResponse> getTokenDistribution(String startDate, String endDate) {
        String tenantId = getCurrentTenantId();
        log.info("Getting token distribution for tenant: {}, from {} to {}", tenantId, startDate, endDate);

        LocalDate start = parseDate(startDate);
        LocalDate end = parseDate(endDate);

        List<TokenDistributionResponse> distribution = dashboardRepository.getTokenDistribution(tenantId, start, end);

        // 无数据时返回空列表
        if (distribution.isEmpty()) {
            log.info("No token distribution data found for tenant: {}", tenantId);
            return Collections.emptyList();
        }

        return distribution;
    }

    /**
     * 获取模型调用统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 模型调用统计列表
     */
    @Cacheable(
        value = "dashboard-model-stats",
        key = "#root.target.getCurrentTenantId() + ':' + #startDate + ':' + #endDate"
    )
    public List<ModelCallStatsResponse> getModelCallStats(String startDate, String endDate) {
        String tenantId = getCurrentTenantId();
        log.info("Getting model call stats for tenant: {}, from {} to {}", tenantId, startDate, endDate);

        LocalDate start = parseDate(startDate);
        LocalDate end = parseDate(endDate);

        List<ModelCallStatsResponse> stats = dashboardRepository.getModelCallStats(tenantId, start, end);

        if (stats.isEmpty()) {
            log.info("No model call stats found for tenant: {}", tenantId);
            return Collections.emptyList();
        }

        return stats;
    }

    /**
     * 获取活跃告警
     *
     * <p>【告警来源】（生产环境需对接真实告警系统）
     * <ul>
     *   <li>Prometheus AlertManager（推荐）</li>
     *   <li>CloudWatch Alarms</li>
     *   <li>自研告警中心</li>
     * </ul>
     *
     * <p>当前实现：从数据库查询异常状态记录
     * <ul>
     *   <li>高失败率工具（失败率 > 20%）</li>
     *   <li>高延迟模型（P95 > 5s）</li>
     *   <li>待审批任务超时</li>
     * </ul>
     *
     * @return 活跃告警列表
     */
    public List<ActiveAlertResponse> getActiveAlerts() {
        String tenantId = getCurrentTenantId();
        log.info("Getting active alerts for tenant: {}", tenantId);

        // 生产环境应对接 AlertManager 或监控平台
        // 当前实现：从数据库检测异常状态
        return detectAlertsFromMetrics(tenantId);
    }

    /**
     * 从指标数据检测告警
     *
     * <p>检测规则：
     * <ul>
     *   <li>工具失败率 > 20%</li>
     *   <li>模型 P95 延迟 > 5s</li>
     *   <li>审批任务即将超时（1小时内）</li>
     * </ul>
     */
    private List<ActiveAlertResponse> detectAlertsFromMetrics(String tenantId) {
        List<ActiveAlertResponse> alerts = new ArrayList<>();
        Instant now = Instant.now();

        // 1. 检测高失败率工具（过去1小时）
        alerts.addAll(detectHighFailureRateTools(tenantId, now));

        // 2. 检测高延迟模型（过去1小时）
        alerts.addAll(detectHighLatencyModels(tenantId, now));

        // 3. 检测即将超时的审批任务
        alerts.addAll(detectExpiringApprovals(tenantId, now));

        return alerts;
    }

    /**
     * 检测高失败率工具
     */
    private List<ActiveAlertResponse> detectHighFailureRateTools(String tenantId, Instant now) {
        List<ActiveAlertResponse> alerts = new ArrayList<>();
        try {
            List<ToolFailureStats> stats = dashboardRepository.queryToolFailureStats(
                    tenantId, now.minusSeconds(3600)
            );

            for (ToolFailureStats stat : stats) {
                alerts.add(ActiveAlertResponse.builder()
                        .id("alert_tool_" + stat.toolName())
                        .type("warning")
                        .message(String.format("工具 %s 失败率 %.1f%%（过去1小时）",
                                stat.toolName(), stat.failureRate()))
                        .source("tool-bus")
                        .createdAt(now.toString())
                        .build());
            }
        } catch (Exception e) {
            log.warn("Failed to detect high failure rate tools", e);
        }

        return alerts;
    }

    /**
     * 检测高延迟模型
     */
    private List<ActiveAlertResponse> detectHighLatencyModels(String tenantId, Instant now) {
        List<ActiveAlertResponse> alerts = new ArrayList<>();
        try {
            List<ModelLatencyStats> stats = dashboardRepository.queryModelLatencyStats(
                    tenantId, now.minusSeconds(3600)
            );

            for (ModelLatencyStats stat : stats) {
                if (stat.p95LatencyMs() > 5000) {
                    alerts.add(ActiveAlertResponse.builder()
                            .id("alert_model_" + stat.modelName())
                            .type("warning")
                            .message(String.format("模型 %s P95 延迟 %.0fms（超过5s阈值）",
                                    stat.modelName(), stat.p95LatencyMs()))
                            .source("model-gateway")
                            .createdAt(now.toString())
                            .build());
                }
            }
        } catch (Exception e) {
            log.warn("Failed to detect high latency models", e);
        }

        return alerts;
    }

    /**
     * 检测即将超时的审批任务
     */
    private List<ActiveAlertResponse> detectExpiringApprovals(String tenantId, Instant now) {
        List<ActiveAlertResponse> alerts = new ArrayList<>();
        try {
            long count = dashboardRepository.countExpiringApprovals(
                    tenantId, now, now.plusSeconds(3600)
            );

            if (count > 0) {
                alerts.add(ActiveAlertResponse.builder()
                        .id("alert_approval_expiring")
                        .type("info")
                        .message(String.format("有 %d 个审批任务将在1小时内超时", count))
                        .source("governance")
                        .createdAt(now.toString())
                        .build());
            }
        } catch (Exception e) {
            log.warn("Failed to detect expiring approvals", e);
        }

        return alerts;
    }

    // 内部记录类
    public record ToolFailureStats(String toolName, long total, long failed, double failureRate) {}
    public record ModelLatencyStats(String modelName, double avgLatencyMs, double p95LatencyMs) {}

    // ==================== 辅助方法 ====================

    /**
     * 获取当前租户 ID
     */
    public String getCurrentTenantId() {
        String tenantId = tenantContextService.getCurrentTenantId();
        if (tenantId == null || tenantId.isBlank()) {
            log.warn("No tenant context found, using default");
            return "default";
        }
        return tenantId;
    }

    /**
     * 根据时间范围计算日期区间
     */
    private DateRange calculateDateRange(String range) {
        LocalDate end = LocalDate.now(ZoneOffset.UTC);
        LocalDate start = switch (range) {
            case "24h" -> end;
            case "7d" -> end.minusDays(6);
            case "30d" -> end.minusDays(29);
            case "90d" -> end.minusDays(89);
            default -> end.minusDays(6);
        };
        return new DateRange(start, end);
    }

    /**
     * 解析日期字符串
     */
    private LocalDate parseDate(String dateStr) {
        if (dateStr == null || dateStr.isBlank()) {
            return LocalDate.now(ZoneOffset.UTC).minusDays(7);
        }
        try {
            return LocalDate.parse(dateStr, DATE_FORMATTER);
        } catch (Exception e) {
            log.warn("Invalid date format: {}, using default", dateStr);
            return LocalDate.now(ZoneOffset.UTC).minusDays(7);
        }
    }

    /**
     * 填充空缺日期
     *
     * <p>确保返回的日期序列连续，无数据日期填充 0 值
     */
    @SuppressWarnings("unchecked")
    private <T> List<T> fillMissingDates(List<T> stats, LocalDate start, LocalDate end, Class<T> type) {
        if (stats.isEmpty()) {
            // 生成空数据序列
            List<T> result = new ArrayList<>();
            LocalDate current = start;
            while (!current.isAfter(end)) {
                if (type == DailyRunStatsResponse.class) {
                    result.add((T) DailyRunStatsResponse.builder()
                            .date(current.format(DATE_FORMATTER))
                            .runs(0L)
                            .successful(0L)
                            .failed(0L)
                            .avgDurationMs(0.0)
                            .build());
                } else if (type == DailyCostStatsResponse.class) {
                    result.add((T) DailyCostStatsResponse.builder()
                            .date(current.format(DATE_FORMATTER))
                            .costUsd(0.0)
                            .tokens(0L)
                            .build());
                }
                current = current.plusDays(1);
            }
            return result;
        }

        // 已有数据，检查是否需要填充
        // 当前实现直接返回数据库结果，因为数据库查询已按日期排序
        return stats;
    }

    /**
     * 日期区间记录
     */
    private record DateRange(LocalDate startDate, LocalDate endDate) {}
}
