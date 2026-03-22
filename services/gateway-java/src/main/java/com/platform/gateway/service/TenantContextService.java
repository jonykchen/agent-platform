package com.platform.gateway.service;

import org.slf4j.MDC;
import org.springframework.stereotype.Service;

/**
 * 租户上下文服务
 */
@Service
public class TenantContextService {

    private static final String TENANT_ID_KEY = "tenant_id";
    private static final String USER_ID_KEY = "user_id";
    private static final String REQUEST_ID_KEY = "request_id";

    /**
     * 设置当前租户和用户上下文
     */
    public void setCurrentTenant(String tenantId, String userId) {
        MDC.put(TENANT_ID_KEY, tenantId);
        MDC.put(USER_ID_KEY, userId);
    }

    /**
     * 设置当前请求 ID
     */
    public void setCurrentRequestId(String requestId) {
        MDC.put(REQUEST_ID_KEY, requestId);
    }

    /**
     * 获取当前租户 ID
     */
    public String getCurrentTenantId() {
        return MDC.get(TENANT_ID_KEY);
    }

    /**
     * 获取当前用户 ID
     */
    public String getCurrentUserId() {
        return MDC.get(USER_ID_KEY);
    }

    /**
     * 获取当前请求 ID
     */
    public String getCurrentRequestId() {
        return MDC.get(REQUEST_ID_KEY);
    }

    /**
     * 清除租户上下文
     */
    public void clear() {
        MDC.remove(TENANT_ID_KEY);
        MDC.remove(USER_ID_KEY);
        MDC.remove(REQUEST_ID_KEY);
    }
}