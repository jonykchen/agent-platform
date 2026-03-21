package com.platform.gateway.exception;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * 业务异常测试
 */
class BusinessExceptionTest {

    @Test
    void businessException_shouldCreateWithErrorCode() {
        ErrorCode errorCode = ErrorCode.ERR_INVALID_REQUEST;
        BusinessException exception = new BusinessException(errorCode);

        assertEquals(errorCode, exception.getErrorCode());
        assertEquals(errorCode.getMessage(), exception.getMessage());
        assertEquals(errorCode.getUserMessage(), exception.getUserMessage());
    }

    @Test
    void businessException_shouldCreateWithCustomMessage() {
        ErrorCode errorCode = ErrorCode.ERR_INVALID_REQUEST;
        String customMessage = "Custom error message";
        BusinessException exception = new BusinessException(errorCode, customMessage);

        assertEquals(errorCode, exception.getErrorCode());
        assertEquals(customMessage, exception.getMessage());
    }

    @Test
    void businessException_shouldCreateWithDetails() {
        ErrorCode errorCode = ErrorCode.ERR_INVALID_REQUEST;
        Object details = "Additional details";
        BusinessException exception = new BusinessException(errorCode, "Error", details);

        assertEquals(errorCode, exception.getErrorCode());
        assertEquals(details, exception.getDetails());
    }

    @Test
    void businessException_shouldCreateWithFactoryMethod() {
        BusinessException exception = BusinessException.of(ErrorCode.ERR_INVALID_REQUEST);

        assertEquals(ErrorCode.ERR_INVALID_REQUEST, exception.getErrorCode());
    }

    @Test
    void businessException_shouldCreateWithFactoryMethodAndMessage() {
        BusinessException exception = BusinessException.of(ErrorCode.ERR_INVALID_REQUEST, "Custom message");

        assertEquals(ErrorCode.ERR_INVALID_REQUEST, exception.getErrorCode());
        assertEquals("Custom message", exception.getMessage());
    }
}