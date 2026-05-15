package com.platform.toolbus.permission;

import com.platform.toolbus.executor.ToolExecutionContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.expression.ExpressionParser;
import org.springframework.expression.spel.standard.SpelExpressionParser;
import org.springframework.expression.spel.support.SimpleEvaluationContext;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;

/**
 * 工具权限检查服务
 *
 * 实现五层权限检查：
 * 1. RBAC 检查 - 角色是否有权调用工具
 * 2. 租户功能开关 - 租户是否开通该工具
 * 3. ABAC 条件 - 动态属性条件检查
 * 4. 频率/额度检查 - 配额限制
 * 5. 风险等级判断 - 是否需要审批
 *
 * 【技术选型】RBAC + ABAC 混合架构
 * ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 *
 * ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
 * │ 方案               │ 优点                        │ 缺点                        │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 纯 RBAC            │ • 简单直观                  │ • 无法处理动态条件          │
 * │                    │ • 管理成本低                │   （金额、部门、时间）      │
 * │                    │                             │ • 角色爆炸问题              │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ 纯 ABAC            │ • 灵活强大                  │ • 规则复杂，性能开销大      │
 * │                    │ • 可处理任意属性组合        │ • 管理成本高                │
 * │                    │                             │ • 调试困难                  │
 * ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
 * │ RBAC + ABAC 混合   │ • 简单场景用 RBAC           │ • 需维护两套体系            │
 * │ (当前选择)         │ • 复杂场景用 ABAC           │ • 设计需明确边界            │
 * │                    │ • 性能可控                  │                              │
 * └────────────────────┴─────────────────────────────┴─────────────────────────────┘
 *
 * 【选择混合架构的原因】
 * 1. 客服场景 90% 是简单权限判断（角色能否调用工具），RBAC 已足够
 * 2. 10% 需动态条件（金额限制、部门限制），ABAC 补充
 * 3. 分层检查：先 RBAC 快速过滤，再 ABAC 精细控制，性能最优
 *
 * 【五层检查顺序的设计依据】
 * 顺序：RBAC → 租户开关 → ABAC → 配额 → 风险等级
 *
 * WHY 这个顺序？
 * - RBAC 第一步：最简单，无 DB 查询可缓存，快速拒绝无权限角色
 * - 租户开关第二步：租户级配置，避免租户未开通的工具被调用
 * - ABAC 第三步：需解析参数，相对复杂，但已通过前两步的请求
 * - 配额第四步：需 Redis 操作，有网络开销，放后面减少无效调用
 * - 风险等级第五步：需综合评估，最复杂，但已通过所有前置检查
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ToolPermissionService {

    private final ToolPermissionRepository permissionRepo;
    private final TenantToolConfigRepository configRepo;
    private final StringRedisTemplate redisTemplate;

    private final ExpressionParser expressionParser = new SpelExpressionParser();

    /**
     * 执行完整的五步权限检查
     *
     * @param toolName 工具名称
     * @param userCtx 用户上下文（包含 tenant_id, user_id, role_name）
     * @param parameters 工具调用参数
     * @throws ToolPermissionDeniedException 任一步骤失败时抛出
     */
    public void validatePermission(String toolName, ToolExecutionContext userCtx, Map<String, Object> parameters) {
        String tenantId = userCtx.getTenantId();
        String roleName = userCtx.getRoleName();

        log.debug("开始权限检查: tool={}, tenant={}, role={}", toolName, tenantId, roleName);

        // Step 1: RBAC 检查
        ToolPermission perm = permissionRepo.findByToolNameAndRoleName(toolName, roleName)
            .orElseThrow(() -> ToolPermissionDeniedException.roleNotAllowed(toolName, roleName));

        log.debug("Step 1 RBAC 通过: allowedActions={}", perm.getAllowedActions());

        // Step 2: 租户功能开关
        TenantToolConfig config = configRepo.findByTenantIdAndToolName(tenantId, toolName)
            .orElseThrow(() -> ToolPermissionDeniedException.toolNotEnabledForTenant(toolName, tenantId));

        if (!config.getIsEnabled()) {
            throw ToolPermissionDeniedException.toolDisabled(toolName, config.getDisabledReason());
        }

        log.debug("Step 2 租户开关通过: enabled=true");

        // Step 3: ABAC 动态条件
        if (perm.getConditions() != null && !perm.getConditions().isEmpty()) {
            evaluateAbacConditions(perm.getConditions(), parameters);
            log.debug("Step 3 ABAC 条件通过");
        }

        // Step 4: 频率/额度检查
        if (config.getDailyQuota() != null) {
            checkDailyQuota(tenantId, toolName, config.getDailyQuota());
            log.debug("Step 4 配额检查通过: dailyQuota={}", config.getDailyQuota());
        }

        log.info("权限检查全部通过: tool={}, tenant={}, role={}", toolName, tenantId, roleName);
    }

    /**
     * 检查是否需要审批
     *
     * @return true 表示需要进入审批流程
     */
    public boolean requiresApproval(String toolName, ToolExecutionContext userCtx) {
        // 查找权限配置
        var permOpt = permissionRepo.findByToolNameAndRoleName(toolName, userCtx.getRoleName());
        if (permOpt.isEmpty()) {
            return true;  // 无权限默认需要审批
        }

        ToolPermission perm = permOpt.get();
        Map<String, Object> conditions = perm.getConditions();

        if (conditions == null || conditions.isEmpty()) {
            return false;
        }

        // 检查显式的审批要求
        Object requiresApproval = conditions.get("requires_approval");
        return requiresApproval != null && Boolean.TRUE.equals(requiresApproval);
    }

    /**
     * 获取工具的最大金额限制
     */
    public Double getMaxAmount(String toolName, String roleName) {
        var permOpt = permissionRepo.findByToolNameAndRoleName(toolName, roleName);
        if (permOpt.isEmpty() || permOpt.get().getConditions() == null) {
            return null;
        }

        Object maxAmount = permOpt.get().getConditions().get("max_amount");
        if (maxAmount instanceof Number) {
            return ((Number) maxAmount).doubleValue();
        }
        return null;
    }

    /**
     * Step 3: ABAC 条件评估（使用 SpEL 沙箱）
     */
    private void evaluateAbacConditions(Map<String, Object> conditions, Map<String, Object> params) {
        if (conditions.isEmpty()) {
            return;
        }

        // 使用安全的 SimpleEvaluationContext（禁止反射、类加载等危险操作）
        SimpleEvaluationContext context = SimpleEvaluationContext.forReadOnlyDataBinding()
            .withRootObject(params)
            .build();

        for (Map.Entry<String, Object> entry : conditions.entrySet()) {
            String conditionKey = entry.getKey();
            Object conditionValue = entry.getValue();

            // 跳过非条件字段
            if (conditionKey.equals("requires_approval")) {
                continue;
            }

            String spelExpression = buildSafeSpelExpression(conditionKey, conditionValue);

            try {
                Boolean result = expressionParser.parseExpression(spelExpression)
                    .getValue(context, Boolean.class);

                if (result == null || !result) {
                    throw ToolPermissionDeniedException.abacConditionFailed(conditionKey);
                }
            } catch (Exception e) {
                log.error("ABAC 评估异常，拒绝访问: condition={}, error={}", conditionKey, e.getMessage());
                throw ToolPermissionDeniedException.abacConditionFailed(conditionKey);
            }
        }
    }

    /**
     * 构建安全的 SpEL 表达式
     */
    private String buildSafeSpelExpression(String key, Object value) {
        return switch (key) {
            case "max_amount" -> String.format("#amount <= %s", safeNumeric(value));
            case "min_amount" -> String.format("#amount >= %s", safeNumeric(value));
            case "allowed_departments" -> String.format("#department in %s", safeList(value));
            case "allowed_regions" -> String.format("#region in %s", safeList(value));
            case "max_quantity" -> String.format("#quantity <= %s", safeNumeric(value));
            default -> {
                log.warn("未知 ABAC 条件键，跳过: {}", key);
                yield "true";
            }
        };
    }

    private String safeNumeric(Object value) {
        if (value instanceof Number n) {
            return n.toString();
        }
        throw new IllegalArgumentException("ABAC 条件值必须是数值");
    }

    @SuppressWarnings("unchecked")
    private String safeList(Object value) {
        if (value instanceof List<?> list) {
            String items = list.stream()
                .filter(item -> item instanceof String)
                .map(item -> "'" + item.toString().replace("'", "''") + "'")
                .reduce((a, b) -> a + ", " + b)
                .orElse("");
            return "{" + items + "}";
        }
        throw new IllegalArgumentException("ABAC 条件值必须是列表");
    }

    /**
     * Step 4: 检查每日配额
     */
    private void checkDailyQuota(String tenantId, String toolName, int dailyQuota) {
        String today = LocalDate.now(ZoneId.of("UTC")).format(DateTimeFormatter.ISO_DATE);
        String key = String.format("quota:tool:%s:%s:%s", tenantId, toolName, today);

        Long current = redisTemplate.opsForValue().increment(key);
        if (current != null && current == 1) {
            // 首次访问，设置过期时间为到当天结束
            long secondsUntilMidnight = getSecondsUntilMidnight();
            redisTemplate.expire(key, secondsUntilMidnight, TimeUnit.SECONDS);
        }

        if (current != null && current > dailyQuota) {
            throw ToolPermissionDeniedException.quotaExceeded(toolName, "每日");
        }
    }

    private long getSecondsUntilMidnight() {
        Instant now = Instant.now();
        Instant midnight = LocalDate.now(ZoneId.of("UTC")).plusDays(1).atStartOfDay(ZoneId.of("UTC")).toInstant();
        return midnight.getEpochSecond() - now.getEpochSecond();
    }

    /**
     * 记录工具调用（用于配额统计）
     */
    public void recordToolCall(String tenantId, String toolName, boolean success, long latencyMs) {
        String today = LocalDate.now(ZoneId.of("UTC")).format(DateTimeFormatter.ISO_DATE);
        String key = String.format("tool_usage:%s:%s:%s", tenantId, toolName, today);

        // 简单统计：总调用数、成功数、失败数
        redisTemplate.opsForHash().increment(key, "total_calls", 1);
        if (success) {
            redisTemplate.opsForHash().increment(key, "success_calls", 1);
        } else {
            redisTemplate.opsForHash().increment(key, "failed_calls", 1);
        }

        // 设置过期时间
        redisTemplate.expire(key, 8, TimeUnit.DAYS);
    }
}
