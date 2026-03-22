package com.platform.gateway.service;

import com.platform.gateway.dto.response.ActiveAlertResponse;
import com.platform.gateway.dto.response.DailyCostStatsResponse;
import com.platform.gateway.dto.response.DailyRunStatsResponse;
import com.platform.gateway.dto.response.DashboardStatsResponse;
import com.platform.gateway.dto.response.ModelCallStatsResponse;
import com.platform.gateway.dto.response.TokenDistributionResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

/**
 * 仪表盘服务
 *
 * MVP 阶段：返回模拟数据，生产环境应连接真实数据库
 */
@Slf4j
@Service
public class DashboardService {

    private static final Random RANDOM = new Random(42); // 固定种子保证数据一致性

    /**
     * 获取仪表盘统计数据
     *
     * @param range 时间范围: 24h, 7d, 30d, 90d
     * @return 统计数据
     */
    public DashboardStatsResponse getStats(String range) {
        log.info("Getting dashboard stats for range: {}", range);

        // 根据时间范围计算倍数
        long multiplier = getMultiplier(range);

        return DashboardStatsResponse.builder()
                .totalSessions(1250L * multiplier / 100)
                .totalRuns(8750L * multiplier / 100)
                .totalTokens(1250000L * multiplier / 100)
                .totalCostUsd(25.50 * multiplier / 100)
                .successRate(96.5)
                .avgResponseTimeMs(1250.0 + RANDOM.nextDouble() * 500)
                .activeUsers(45L + multiplier / 10)
                .pendingApprovals(3L)
                .build();
    }

    /**
     * 获取每日运行统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 每日运行统计列表
     */
    public List<DailyRunStatsResponse> getDailyRunStats(String startDate, String endDate) {
        log.info("Getting daily run stats from {} to {}", startDate, endDate);

        List<DailyRunStatsResponse> result = new ArrayList<>();
        LocalDate start = parseDate(startDate);
        LocalDate end = parseDate(endDate);

        LocalDate current = start;
        while (!current.isAfter(end)) {
            long runs = 50 + RANDOM.nextInt(100);
            long successful = (long) (runs * (0.92 + RANDOM.nextDouble() * 0.06));
            long failed = runs - successful;

            result.add(DailyRunStatsResponse.builder()
                    .date(current.format(DateTimeFormatter.ISO_LOCAL_DATE))
                    .runs(runs)
                    .successful(successful)
                    .failed(failed)
                    .avgDurationMs(1000.0 + RANDOM.nextDouble() * 1000)
                    .build());

            current = current.plusDays(1);
        }

        return result;
    }

    /**
     * 获取每日成本统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 每日成本统计列表
     */
    public List<DailyCostStatsResponse> getDailyCostStats(String startDate, String endDate) {
        log.info("Getting daily cost stats from {} to {}", startDate, endDate);

        List<DailyCostStatsResponse> result = new ArrayList<>();
        LocalDate start = parseDate(startDate);
        LocalDate end = parseDate(endDate);

        LocalDate current = start;
        while (!current.isAfter(end)) {
            long tokens = 10000 + RANDOM.nextInt(20000);
            double costUsd = tokens * 0.00002; // 假设每 token $0.00002

            result.add(DailyCostStatsResponse.builder()
                    .date(current.format(DateTimeFormatter.ISO_LOCAL_DATE))
                    .costUsd(Math.round(costUsd * 100.0) / 100.0)
                    .tokens(tokens)
                    .build());

            current = current.plusDays(1);
        }

        return result;
    }

    /**
     * 获取 Token 分布
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return Token 分布列表
     */
    public List<TokenDistributionResponse> getTokenDistribution(String startDate, String endDate) {
        log.info("Getting token distribution from {} to {}", startDate, endDate);

        List<TokenDistributionResponse> result = new ArrayList<>();

        // 模拟各模型的 Token 使用分布
        String[] models = {
                "deepseek-chat",
                "qwen-max",
                "doubao-pro-32k",
                "glm-4",
                "yi-large"
        };

        long[] tokens = {45000, 32000, 28000, 18000, 12000};
        long totalTokens = 135000;
        double[] costs = {0.90, 0.96, 0.56, 0.54, 0.24};

        for (int i = 0; i < models.length; i++) {
            result.add(TokenDistributionResponse.builder()
                    .model(models[i])
                    .tokens(tokens[i])
                    .percentage(Math.round(tokens[i] * 1000.0 / totalTokens) / 10.0)
                    .costUsd(costs[i])
                    .build());
        }

        return result;
    }

    /**
     * 获取模型调用统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 模型调用统计列表
     */
    public List<ModelCallStatsResponse> getModelCallStats(String startDate, String endDate) {
        log.info("Getting model call stats from {} to {}", startDate, endDate);

        List<ModelCallStatsResponse> result = new ArrayList<>();

        // 模拟各模型的调用统计
        result.add(ModelCallStatsResponse.builder()
                .model("deepseek-chat")
                .totalCalls(1250L)
                .successRate(98.2)
                .avgLatencyMs(850.0)
                .totalTokens(45000L)
                .costUsd(0.90)
                .build());

        result.add(ModelCallStatsResponse.builder()
                .model("qwen-max")
                .totalCalls(890L)
                .successRate(97.5)
                .avgLatencyMs(1200.0)
                .totalTokens(32000L)
                .costUsd(0.96)
                .build());

        result.add(ModelCallStatsResponse.builder()
                .model("doubao-pro-32k")
                .totalCalls(720L)
                .successRate(96.8)
                .avgLatencyMs(1100.0)
                .totalTokens(28000L)
                .costUsd(0.56)
                .build());

        result.add(ModelCallStatsResponse.builder()
                .model("glm-4")
                .totalCalls(450L)
                .successRate(95.5)
                .avgLatencyMs(950.0)
                .totalTokens(18000L)
                .costUsd(0.54)
                .build());

        result.add(ModelCallStatsResponse.builder()
                .model("yi-large")
                .totalCalls(280L)
                .successRate(94.2)
                .avgLatencyMs(1050.0)
                .totalTokens(12000L)
                .costUsd(0.24)
                .build());

        return result;
    }

    /**
     * 获取活跃告警
     *
     * @return 活跃告警列表
     */
    public List<ActiveAlertResponse> getActiveAlerts() {
        log.info("Getting active alerts");

        List<ActiveAlertResponse> result = new ArrayList<>();
        Instant now = Instant.now();

        // 模拟告警数据
        result.add(ActiveAlertResponse.builder()
                .id("alert_001")
                .type("warning")
                .message("模型 deepseek-chat 响应延迟超过阈值 (P95 > 3s)")
                .source("model-gateway")
                .createdAt(now.minusSeconds(1800).toString())
                .build());

        result.add(ActiveAlertResponse.builder()
                .id("alert_002")
                .type("error")
                .message("工具调用失败率上升: query_order_status 成功率 85%")
                .source("tool-bus")
                .createdAt(now.minusSeconds(3600).toString())
                .build());

        result.add(ActiveAlertResponse.builder()
                .id("alert_003")
                .type("info")
                .message("租户 tenant_001 配额使用率达到 80%")
                .source("governance")
                .createdAt(now.minusSeconds(7200).toString())
                .build());

        return result;
    }

    /**
     * 根据时间范围获取倍数
     */
    private long getMultiplier(String range) {
        if (range == null) {
            return 100;
        }
        return switch (range) {
            case "24h" -> 100;
            case "7d" -> 700;
            case "30d" -> 3000;
            case "90d" -> 9000;
            default -> 100;
        };
    }

    /**
     * 解析日期字符串，如果无效则返回默认值
     */
    private LocalDate parseDate(String dateStr) {
        if (dateStr == null || dateStr.isBlank()) {
            return LocalDate.now(ZoneOffset.UTC).minusDays(7);
        }
        try {
            return LocalDate.parse(dateStr, DateTimeFormatter.ISO_LOCAL_DATE);
        } catch (Exception e) {
            log.warn("Invalid date format: {}, using default", dateStr);
            return LocalDate.now(ZoneOffset.UTC).minusDays(7);
        }
    }
}
