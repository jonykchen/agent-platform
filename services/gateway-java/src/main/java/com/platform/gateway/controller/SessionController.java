package com.platform.gateway.controller;

import com.platform.gateway.dto.request.CreateSessionRequest;
import com.platform.gateway.dto.request.SessionListRequest;
import com.platform.gateway.dto.request.UpdateTitleRequest;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.SessionResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.SessionService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

/**
 * 会话管理控制器
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/sessions")
@RequiredArgsConstructor
public class SessionController {

    private final SessionService sessionService;

    /**
     * 查询会话列表
     * GET /api/v1/sessions
     */
    @GetMapping
    public ResponseEntity<PageResponse<SessionResponse>> listSessions(
            @Valid SessionListRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("List sessions request: requestId={}, status={}, page={}, size={}",
                requestId, request.getStatus(), request.getPageNumber(), request.getPageSize());

        try {
            PageResponse<SessionResponse> response = sessionService.listSessions(request);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("List sessions error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to list sessions");
        }
    }

    /**
     * 创建会话
     * POST /api/v1/sessions
     */
    @PostMapping
    public ResponseEntity<SessionResponse> createSession(
            @Valid @RequestBody CreateSessionRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Create session request: requestId={}, type={}", requestId, request.getSessionType());

        try {
            SessionResponse response = sessionService.createSession(request);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Create session error: requestId={}", requestId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to create session");
        }
    }

    /**
     * 获取单个会话
     * GET /api/v1/sessions/{id}
     */
    @GetMapping("/{id}")
    public ResponseEntity<SessionResponse> getSession(@PathVariable UUID id) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("Get session request: requestId={}, sessionId={}", requestId, id);

        try {
            SessionResponse response = sessionService.getSession(id);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Get session error: requestId={}, sessionId={}", requestId, id, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to get session");
        }
    }

    /**
     * 删除会话
     * DELETE /api/v1/sessions/{id}
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> deleteSession(@PathVariable UUID id) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Delete session request: requestId={}, sessionId={}", requestId, id);

        try {
            sessionService.deleteSession(id);
            return ResponseEntity.noContent().build();
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Delete session error: requestId={}, sessionId={}", requestId, id, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to delete session");
        }
    }

    /**
     * 更新会话标题
     * PATCH /api/v1/sessions/{id}
     */
    @PatchMapping("/{id}")
    public ResponseEntity<SessionResponse> updateTitle(
            @PathVariable UUID id,
            @Valid @RequestBody UpdateTitleRequest request) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Update session title request: requestId={}, sessionId={}", requestId, id);

        try {
            SessionResponse response = sessionService.updateTitle(id, request.getTitle());
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Update session title error: requestId={}, sessionId={}", requestId, id, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to update session title");
        }
    }

    /**
     * 归档会话
     * POST /api/v1/sessions/{id}/archive
     */
    @PostMapping("/{id}/archive")
    public ResponseEntity<SessionResponse> archiveSession(@PathVariable UUID id) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Archive session request: requestId={}, sessionId={}", requestId, id);

        try {
            SessionResponse response = sessionService.archiveSession(id);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Archive session error: requestId={}, sessionId={}", requestId, id, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to archive session");
        }
    }

    /**
     * 取消归档会话
     * POST /api/v1/sessions/{id}/unarchive
     */
    @PostMapping("/{id}/unarchive")
    public ResponseEntity<SessionResponse> unarchiveSession(@PathVariable UUID id) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Unarchive session request: requestId={}, sessionId={}", requestId, id);

        try {
            SessionResponse response = sessionService.unarchiveSession(id);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Unarchive session error: requestId={}, sessionId={}", requestId, id, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to unarchive session");
        }
    }
}