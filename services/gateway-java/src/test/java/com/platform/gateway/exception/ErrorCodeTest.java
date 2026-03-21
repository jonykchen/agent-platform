package com.platform.gateway.exception;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 错误码枚举测试
 */
class ErrorCodeTest {

    @Test
    void errorCode_shouldHaveCorrectProperties() {
        ErrorCode error = ErrorCode.ERR_INVALID_REQUEST;

        assertEquals("ERR_INVALID_REQUEST", error.getCode());
        assertEquals("Invalid request", error.getMessage());
        assertEquals("请求参数有误", error.getUserMessage());
        assertEquals(400, error.getHttpStatus());
    }

    @Test
    void errorCode_shouldHaveUnauthorizedError() {
        ErrorCode error = ErrorCode.ERR_UNAUTHORIZED;

        assertEquals(401, error.getHttpStatus());
        assertEquals("ERR_UNAUTHORIZED", error.getCode());
    }

    @Test
    void errorCode_shouldHaveNotFoundError() {
        ErrorCode error = ErrorCode.ERR_NOT_FOUND;

        assertEquals(404, error.getHttpStatus());
        assertEquals("ERR_NOT_FOUND", error.getCode());
    }

    @Test
    void errorCode_shouldHaveRateLimitedError() {
        ErrorCode error = ErrorCode.ERR_RATE_LIMITED;

        assertEquals(429, error.getHttpStatus());
        assertEquals("ERR_RATE_LIMITED", error.getCode());
    }

    @Test
    void errorCode_shouldHaveAgentErrors() {
        ErrorCode error = ErrorCode.ERR_AGENT_MAX_STEPS_EXCEEDED;

        assertEquals(400, error.getHttpStatus());
        assertEquals("ERR_AGENT_MAX_STEPS_EXCEEDED", error.getCode());
    }

    @Test
    void errorCode_shouldHaveModelErrors() {
        ErrorCode error = ErrorCode.ERR_MODEL_ALL_PROVIDERS_DOWN;

        assertEquals(503, error.getHttpStatus());
        assertEquals("ERR_MODEL_ALL_PROVIDERS_DOWN", error.getCode());
    }

    @Test
    void errorCode_shouldHaveToolErrors() {
        ErrorCode error = ErrorCode.ERR_TOOL_VALIDATION_FAILED;

        assertEquals(400, error.getHttpStatus());
        assertEquals("ERR_TOOL_VALIDATION_FAILED", error.getCode());
    }

    @Test
    void errorCode_shouldHaveQuotaError() {
        ErrorCode error = ErrorCode.ERR_TENANT_QUOTA_EXCEEDED;

        assertEquals(429, error.getHttpStatus());
        assertEquals("ERR_TENANT_QUOTA_EXCEEDED", error.getCode());
    }
}