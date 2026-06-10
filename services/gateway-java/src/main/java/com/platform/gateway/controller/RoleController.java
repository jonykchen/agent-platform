package com.platform.gateway.controller;

import com.platform.gateway.dto.response.RoleResponse;
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
 * 角色控制器
 * 提供角色列表查询接口
 */
@Slf4j
@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
@PreAuthorize("hasRole('admin')")  // 角色管理为管理员专属
public class RoleController {

    private final UserService userService;

    /**
     * 获取角色列表
     * GET /api/v1/roles
     */
    @GetMapping("/roles")
    public ResponseEntity<List<RoleResponse>> getRoles() {
        String requestId = RequestIdGenerator.getCurrent();

        log.debug("getRoles request: requestId={}", requestId);

        try {
            List<RoleResponse> response = userService.getRoles();
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("getRoles error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "User service unavailable");
        }
    }
}
