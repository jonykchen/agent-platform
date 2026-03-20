package com.platform.gateway.exception;

import lombok.Getter;

/**
 * 业务异常基类
 */
@Getter
public class BusinessException extends RuntimeException {

    private final ErrorCode errorCode;
    private final String userMessage;
    private final Object details;

    public BusinessException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
        this.userMessage = errorCode.getUserMessage();
        this.details = null;
    }

    public BusinessException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
        this.userMessage = errorCode.getUserMessage();
        this.details = null;
    }

    public BusinessException(ErrorCode errorCode, String message, Object details) {
        super(message);
        this.errorCode = errorCode;
        this.userMessage = errorCode.getUserMessage();
        this.details = details;
    }

    public static BusinessException of(ErrorCode errorCode) {
        return new BusinessException(errorCode);
    }

    public static BusinessException of(ErrorCode errorCode, String message) {
        return new BusinessException(errorCode, message);
    }

    public static BusinessException of(ErrorCode errorCode, String message, Object details) {
        return new BusinessException(errorCode, message, details);
    }
}
