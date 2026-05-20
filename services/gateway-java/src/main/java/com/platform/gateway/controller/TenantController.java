package com.platform.gateway.controller;

import com.platform.gateway.dto.request.UpdateSettingsRequest;
import com.platform.gateway.dto.response.ModelResponse;
import com.platform.gateway.dto.response.QuotaUsageResponse;
import com.platform.gateway.dto.response.TenantConfigResponse;
import com.platform.gateway.dto.response.UsageResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.TenantContextService;
import com.platform.gateway.service.TenantService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 租户管理控制器
 *
 * <p>【核心职责】
 * <ul>
 *   <li>提供租户配置查询接口</li>
 *   <li>提供配额使用情况查询</li>
 *   <li>提供用量统计查询</li>
 *   <li>提供可用模型列表查询</li>
 *   <li>支持租户设置更新和重置</li>
 * </ul>
 *
 * <p>【API 端点列表】
 * <pre>
 * ┌──────────────────────────────────────────────────────────────────────────────┐
 * │ 方法   │ 路径                                      │ 描述             │ 权限      │
 * ├────────┼───────────────────────────────────────────┼──────────────────┼───────────┤
 * │ GET    │ /api/v1/tenants/{tenantId}                │ 获取租户配置     │ tenant:read   │
 * │ GET    │ /api/v1/tenants/{tenantId}/quota          │ 获取配额使用情况 │ tenant:read   │
 * │ GET    │ /api/v1/tenants/{tenantId}/usage          │ 获取用量统计     │ tenant:read   │
 * │ GET    │ /api/v1/tenants/models                    │ 获取可用模型列表 │ public    │
 * │ PATCH  │ /api/v1/tenants/{tenantId}/settings       │ 更新租户设置     │ tenant:write  │
 * │ POST   │ /api/v1/tenants/{tenantId}/settings/reset │ 重置为默认配置   │ tenant:write  │
 * └────────┴───────────────────────────────────────────┴──────────────────┴───────────┘
 * </pre>
 *
 * <p>【安全说明】
 * <ul>
 *   <li>租户隔离：所有操作自动验证 tenantId，确保数据隔离</li>
 *   <li>权限控制：写操作需要 tenant:write 权限</li>
 *   <li>审计追踪：所有写操作记录审计日志</li>
 * </ul>
 *
 * <p>【日志规范】
 * <ul>
 *   <li>INFO: 写操作（更新、重置）</li>
 *   <li>DEBUG: 读操作（查询配置、配额、用量）</li>
 *   <li>WARN: 业务异常</li>
 *   <li>ERROR: 系统异常</li>
 * </ul>
 *
 * @see TenantService
 * @see TenantContextService
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/tenants")
@RequiredArgsConstructor
public class TenantController {

    private final TenantService tenantService;
    private final TenantContextService tenantContextService;

    /**
     * 获取租户配置
     *
     * <p>【功能说明】
     * 获取指定租户的完整配置信息，包括配额、功能开关等。
     *
     * <p>【权限要求】tenant:read
     *
     * <p>【审计标记】
     * <ul>
     *   <li>操作类型：QUERY</li>
     *   <li>审计字段：tenantId, operatorId, queryTime</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @return 租户配置响应
     * @throws BusinessException 当租户不存在或无权访问时抛出
     */
    @GetMapping("/{tenantId}")
    public ResponseEntity<TenantConfigResponse> getTenantConfig(@PathVariable String tenantId) {
        String requestId = RequestIdGenerator.getCurrent();
        String currentTenantId = tenantContextService.getCurrentTenantId();

        log.info("getTenantConfig request: requestId={}, tenantId={}, currentTenantId={}",
                requestId, tenantId, currentTenantId);

        // 租户隔离验证：确保只能查询当前租户的配置
        validateTenantAccess(tenantId, currentTenantId);

        try {
            TenantConfigResponse response = tenantService.getTenantConfig(tenantId);
            log.info("getTenantConfig success: requestId={}, tenantId={}", requestId, tenantId);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("getTenantConfig failed: requestId={}, tenantId={}, error={}",
                    requestId, tenantId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("getTenantConfig error: requestId={}, tenantId={}", requestId, tenantId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Tenant service unavailable");
        }
    }

    /**
     * 获取租户配额使用情况
     *
     * <p>【功能说明】
     * 获取指定租户的配额使用情况，包括 Token、会话、用户、API Key 等。
     *
     * <p>【权限要求】tenant:read
     *
     * <p>【审计标记】
     * <ul>
     *   <li>操作类型：QUERY</li>
     *   <li>审计字段：tenantId, operatorId, queryTime</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @return 配额使用情况响应
     * @throws BusinessException 当租户不存在或无权访问时抛出
     */
    @GetMapping("/{tenantId}/quota")
    public ResponseEntity<QuotaUsageResponse> getQuotaUsage(@PathVariable String tenantId) {
        String requestId = RequestIdGenerator.getCurrent();
        String currentTenantId = tenantContextService.getCurrentTenantId();

        log.info("getQuotaUsage request: requestId={}, tenantId={}, currentTenantId={}",
                requestId, tenantId, currentTenantId);

        // 租户隔离验证
        validateTenantAccess(tenantId, currentTenantId);

        try {
            QuotaUsageResponse response = tenantService.getQuotaUsage(tenantId);
            log.info("getQuotaUsage success: requestId={}, tenantId={}", requestId, tenantId);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("getQuotaUsage failed: requestId={}, tenantId={}, error={}",
                    requestId, tenantId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("getQuotaUsage error: requestId={}, tenantId={}", requestId, tenantId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Tenant service unavailable");
        }
    }

    /**
     * 获取租户用量统计
     *
     * <p>【功能说明】
     * 获取指定租户的用量统计数据，包括 Token 消耗、请求次数、模型调用等。
     *
     * <p>【权限要求】tenant:read
     *
     * <p>【审计标记】
     * <ul>
     *   <li>操作类型：QUERY</li>
     *   <li>审计字段：tenantId, operatorId, queryTime</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @return 用量统计响应
     * @throws BusinessException 当租户不存在或无权访问时抛出
     */
    @GetMapping("/{tenantId}/usage")
    public ResponseEntity<UsageResponse> getUsage(@PathVariable String tenantId) {
        String requestId = RequestIdGenerator.getCurrent();
        String currentTenantId = tenantContextService.getCurrentTenantId();

        log.info("getUsage request: requestId={}, tenantId={}, currentTenantId={}",
                requestId, tenantId, currentTenantId);

        // 租户隔离验证
        validateTenantAccess(tenantId, currentTenantId);

        try {
            UsageResponse response = tenantService.getUsage(tenantId);
            log.info("getUsage success: requestId={}, tenantId={}", requestId, tenantId);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            log.warn("getUsage failed: requestId={}, tenantId={}, error={}",
                    requestId, tenantId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("getUsage error: requestId={}, tenantId={}", requestId, tenantId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Tenant service unavailable");
        }
    }

    /**
     * 获取可用模型列表
     *
     * <p>【功能说明】
     * 获取平台支持的所有可用模型列表，包括模型信息和能力。
     *
     * <p>【权限要求】无需权限（公开接口）
     *
     * @return 模型列表
     */
    @GetMapping("/models")
    public ResponseEntity<List<ModelResponse>> getAvailableModels() {
        String requestId = RequestIdGenerator.getCurrent();

        log.info("getAvailableModels request: requestId={}", requestId);

        try {
            List<ModelResponse> response = tenantService.getAvailableModels();
            log.info("getAvailableModels success: requestId={}, count={}", requestId, response.size());
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("getAvailableModels error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Tenant service unavailable");
        }
    }

    /**
     * 更新租户设置
     *
     * <p>【功能说明】
     * 部分更新租户设置（PATCH 语义）。仅更新请求中提供的字段。
     *
     * <p>【权限要求】tenant:write
     *
     * <p>【审计标记】
     * <ul>
     *   <li>操作类型：UPDATE</li>
     *   <li>审计字段：tenantId, operatorId, changedFields, updateTime</li>
     *   <li>重要：此操作会写入审计日志，不可删除</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @param request 更新请求
     * @return 空响应
     * @throws BusinessException 当租户不存在、无权访问或参数校验失败时抛出
     */
    @PatchMapping("/{tenantId}/settings")
    public ResponseEntity<Void> updateSettings(
            @PathVariable String tenantId,
            @Valid @RequestBody UpdateSettingsRequest request) {

        String requestId = RequestIdGenerator.getCurrent();
        String currentTenantId = tenantContextService.getCurrentTenantId();

        log.info("updateSettings request: requestId={}, tenantId={}, currentTenantId={}",
                requestId, tenantId, currentTenantId);

        // 租户隔离验证
        validateTenantAccess(tenantId, currentTenantId);

        try {
            tenantService.updateSettings(tenantId, request);
            log.info("updateSettings success: requestId={}, tenantId={}", requestId, tenantId);
            return ResponseEntity.ok().build();
        } catch (BusinessException e) {
            log.warn("updateSettings failed: requestId={}, tenantId={}, error={}",
                    requestId, tenantId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("updateSettings error: requestId={}, tenantId={}", requestId, tenantId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Tenant service unavailable");
        }
    }

    /**
     * 重置为默认配置
     *
     * <p>【功能说明】
     * 将租户设置重置为系统默认配置。
     *
     * <p>【权限要求】tenant:write
     *
     * <p>【审计标记】
     * <ul>
     *   <li>操作类型：RESET</li>
     *   <li>审计字段：tenantId, operatorId, actionTime</li>
     *   <li>重要：此操作会写入审计日志，不可删除</li>
     * </ul>
     *
     * @param tenantId 租户ID
     * @return 空响应
     * @throws BusinessException 当租户不存在或无权访问时抛出
     */
    @PostMapping("/{tenantId}/settings/reset")
    public ResponseEntity<Void> resetSettings(@PathVariable String tenantId) {
        String requestId = RequestIdGenerator.getCurrent();
        String currentTenantId = tenantContextService.getCurrentTenantId();

        log.info("resetSettings request: requestId={}, tenantId={}, currentTenantId={}",
                requestId, tenantId, currentTenantId);

        // 租户隔离验证
        validateTenantAccess(tenantId, currentTenantId);

        try {
            tenantService.resetSettings(tenantId);
            log.info("resetSettings success: requestId={}, tenantId={}", requestId, tenantId);
            return ResponseEntity.ok().build();
        } catch (BusinessException e) {
            log.warn("resetSettings failed: requestId={}, tenantId={}, error={}",
                    requestId, tenantId, e.getMessage());
            throw e;
        } catch (Exception e) {
            log.error("resetSettings error: requestId={}, tenantId={}", requestId, tenantId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Tenant service unavailable");
        }
    }

    /**
     * 验证租户访问权限
     *
     * <p>确保请求的 tenantId 与当前上下文中的 tenantId 一致，
     * 防止跨租户访问。
     *
     * @param requestedTenantId 请求的租户ID
     * @param currentTenantId 当前用户的租户ID
     * @throws BusinessException 当租户ID不匹配时抛出
     */
    private void validateTenantAccess(String requestedTenantId, String currentTenantId) {
        if (!requestedTenantId.equals(currentTenantId)) {
            log.warn("Tenant access denied: requested={}, current={}",
                    requestedTenantId, currentTenantId);
            throw BusinessException.of(ErrorCode.ERR_FORBIDDEN, "Access denied to this tenant");
        }
    }
}
