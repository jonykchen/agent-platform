package com.platform.gateway.controller;

import com.platform.gateway.dto.response.ActiveAlertResponse;
import com.platform.gateway.dto.response.DailyCostStatsResponse;
import com.platform.gateway.dto.response.DailyRunStatsResponse;
import com.platform.gateway.dto.response.DashboardStatsResponse;
import com.platform.gateway.dto.response.ModelCallStatsResponse;
import com.platform.gateway.dto.response.TokenDistributionResponse;
import com.platform.gateway.service.DashboardService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.List;

/**
 * 仪表盘控制器
 *
 * 提供仪表盘统计数据查询接口
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/dashboard")
@RequiredArgsConstructor
public class DashboardController {

    private final DashboardService dashboardService;

    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ISO_LOCAL_DATE;

    /**
     * 获取仪表盘统计数据
     *
     * @param range 时间范围: 24h, 7d, 30d, 90d
     * @return 统计数据
     */
    @GetMapping("/stats")
    public ResponseEntity<DashboardStatsResponse> getStats(
            @RequestParam(value = "range", required = false, defaultValue = "24h") String range) {
        log.info("Get dashboard stats request, range: {}", range);
        return ResponseEntity.ok(dashboardService.getStats(range));
    }

    /**
     * 获取每日运行统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 每日运行统计列表
     */
    @GetMapping("/runs/daily")
    public ResponseEntity<List<DailyRunStatsResponse>> getDailyRunStats(
            @RequestParam(value = "start_date", required = false) String startDate,
            @RequestParam(value = "end_date", required = false) String endDate) {
        log.info("Get daily run stats request, start: {}, end: {}", startDate, endDate);

        // 如果未提供日期，默认返回最近 7 天
        LocalDate end = parseDate(endDate, LocalDate.now());
        LocalDate start = parseDate(startDate, end.minusDays(6));

        return ResponseEntity.ok(dashboardService.getDailyRunStats(
                start.format(DATE_FORMATTER),
                end.format(DATE_FORMATTER)));
    }

    /**
     * 获取每日成本统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 每日成本统计列表
     */
    @GetMapping("/costs/daily")
    public ResponseEntity<List<DailyCostStatsResponse>> getDailyCostStats(
            @RequestParam(value = "start_date", required = false) String startDate,
            @RequestParam(value = "end_date", required = false) String endDate) {
        log.info("Get daily cost stats request, start: {}, end: {}", startDate, endDate);

        LocalDate end = parseDate(endDate, LocalDate.now());
        LocalDate start = parseDate(startDate, end.minusDays(6));

        return ResponseEntity.ok(dashboardService.getDailyCostStats(
                start.format(DATE_FORMATTER),
                end.format(DATE_FORMATTER)));
    }

    /**
     * 获取 Token 分布
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return Token 分布列表
     */
    @GetMapping("/tokens/distribution")
    public ResponseEntity<List<TokenDistributionResponse>> getTokenDistribution(
            @RequestParam(value = "start_date", required = false) String startDate,
            @RequestParam(value = "end_date", required = false) String endDate) {
        log.info("Get token distribution request, start: {}, end: {}", startDate, endDate);

        LocalDate end = parseDate(endDate, LocalDate.now());
        LocalDate start = parseDate(startDate, end.minusDays(6));

        return ResponseEntity.ok(dashboardService.getTokenDistribution(
                start.format(DATE_FORMATTER),
                end.format(DATE_FORMATTER)));
    }

    /**
     * 获取模型调用统计
     *
     * @param startDate 开始日期 (YYYY-MM-DD)
     * @param endDate   结束日期 (YYYY-MM-DD)
     * @return 模型调用统计列表
     */
    @GetMapping("/models/stats")
    public ResponseEntity<List<ModelCallStatsResponse>> getModelCallStats(
            @RequestParam(value = "start_date", required = false) String startDate,
            @RequestParam(value = "end_date", required = false) String endDate) {
        log.info("Get model call stats request, start: {}, end: {}", startDate, endDate);

        LocalDate end = parseDate(endDate, LocalDate.now());
        LocalDate start = parseDate(startDate, end.minusDays(6));

        return ResponseEntity.ok(dashboardService.getModelCallStats(
                start.format(DATE_FORMATTER),
                end.format(DATE_FORMATTER)));
    }

    /**
     * 获取活跃告警
     *
     * @return 活跃告警列表
     */
    @GetMapping("/alerts")
    public ResponseEntity<List<ActiveAlertResponse>> getActiveAlerts() {
        log.info("Get active alerts request");
        return ResponseEntity.ok(dashboardService.getActiveAlerts());
    }

    /**
     * 解析日期字符串
     *
     * @param dateStr     日期字符串 (YYYY-MM-DD)
     * @param defaultVal  默认值
     * @return 解析后的日期或默认值
     */
    private LocalDate parseDate(String dateStr, LocalDate defaultVal) {
        if (dateStr == null || dateStr.isBlank()) {
            return defaultVal;
        }
        try {
            return LocalDate.parse(dateStr, DATE_FORMATTER);
        } catch (Exception e) {
            log.warn("Invalid date format: {}, using default", dateStr);
            return defaultVal;
        }
    }
}