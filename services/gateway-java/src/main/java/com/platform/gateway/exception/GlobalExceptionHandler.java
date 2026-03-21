package com.platform.gateway.exception;

import com.platform.gateway.dto.response.ErrorResponse;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

/**
 * 全局异常处理器
 */
@Slf4j
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusinessException(BusinessException ex) {
        log.warn("Business error: code={}, msg={}", ex.getErrorCode().getCode(), ex.getMessage());

        ErrorResponse response = ErrorResponse.builder()
                .error(ex.getErrorCode().getCode())
                .message(ex.getMessage())
                .userMessage(ex.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .details(ex.getDetails())
                .build();

        return ResponseEntity.status(ex.getErrorCode().getHttpStatus()).body(response);
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<ErrorResponse> handleIllegalArgument(IllegalArgumentException ex) {
        log.warn("Invalid argument: {}", ex.getMessage());

        ErrorResponse response = ErrorResponse.builder()
                .error(ErrorCode.ERR_INVALID_REQUEST.getCode())
                .message(ex.getMessage())
                .userMessage(ErrorCode.ERR_INVALID_REQUEST.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .build();

        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(response);
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnexpected(Exception ex) {
        log.error("Unexpected error", ex);

        ErrorResponse response = ErrorResponse.builder()
                .error(ErrorCode.ERR_UNKNOWN.getCode())
                .message("Internal server error")
                .userMessage(ErrorCode.ERR_UNKNOWN.getUserMessage())
                .requestId(RequestIdGenerator.getCurrent())
                .build();

        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(response);
    }
}