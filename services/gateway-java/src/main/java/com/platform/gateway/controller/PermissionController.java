package com.platform.gateway.controller;

import com.platform.gateway.dto.response.PermissionResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.UserService;
import com.platform.gateway.util.RequestIdGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 权限控制器
 * 提供权限列表查询接口
 */
@Slf4j
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@PreAuthorize("hasRole('admin')")  // 权限管理为管理员专属
public class PermissionController {

    private final UserService userService;

    /**
     * 获取权限列表
     * GET /api/v1/permissions
     */
    @GetMapping("/permissions")
    public ResponseEntity<List<PermissionResponse>> getPermissions() {
        String requestId = RequestIdGenerator.getCurrent();

        log.debug("getPermissions request: requestId={}", requestId);

        try {
            List<PermissionResponse> response = userService.getPermissions();
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("getPermissions error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }
}
