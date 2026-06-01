package com.platform.gateway.controller;

import com.platform.gateway.audit.AuditLog;
import com.platform.gateway.dto.request.CreateSessionRequest;
import com.platform.gateway.dto.request.SessionListRequest;
import com.platform.gateway.dto.request.UpdateTitleRequest;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.RunDetailResponse;
import com.platform.gateway.dto.response.RunResponse;
import com.platform.gateway.dto.response.SessionResponse;
import com.platform.gateway.dto.response.StepResponse;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.service.SessionService;
import com.platform.gateway.util.RequestIdGenerator;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
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
    @AuditLog(
        type = "session.created",
        category = "lifecycle",
        action = "创建会话",
        resourceType = "session",
        severity = "info",
        logResult = true
    )
    public ResponseEntity<SessionResponse> createSession(
            @RequestBody(required = false) CreateSessionRequest request) {
        String requestId = RequestIdGenerator.getCurrent();

        // 如果请求体为空，使用默认值
        if (request == null) {
            request = new CreateSessionRequest();
        }

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
    @AuditLog(
        type = "session.deleted",
        category = "lifecycle",
        action = "删除会话",
        resourceType = "session",
        severity = "warn"
    )
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
    @AuditLog(
        type = "session.archived",
        category = "lifecycle",
        action = "归档会话",
        resourceType = "session",
        severity = "info"
    )
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

    // ==================== Run 相关接口 ====================

    /**
     * 获取会话的所有 Run
     * GET /api/v1/sessions/{sessionId}/runs
     */
    @GetMapping("/{sessionId}/runs")
    public ResponseEntity<PageResponse<RunResponse>> getSessionRuns(
            @PathVariable UUID sessionId,
            @RequestParam(defaultValue = "1") Integer pageNumber,
            @RequestParam(defaultValue = "20") Integer pageSize) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("Get session runs request: requestId={}, sessionId={}, page={}, size={}",
                requestId, sessionId, pageNumber, pageSize);

        try {
            PageResponse<RunResponse> response = sessionService.getSessionRuns(sessionId, pageNumber, pageSize);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Get session runs error: requestId={}, sessionId={}", requestId, sessionId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to get session runs");
        }
    }

    /**
     * 获取单个 Run 详情
     * GET /api/v1/sessions/{sessionId}/runs/{runId}
     */
    @GetMapping("/{sessionId}/runs/{runId}")
    public ResponseEntity<RunDetailResponse> getRun(
            @PathVariable UUID sessionId,
            @PathVariable UUID runId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("Get run request: requestId={}, sessionId={}, runId={}", requestId, sessionId, runId);

        try {
            RunDetailResponse response = sessionService.getRun(sessionId, runId);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Get run error: requestId={}, sessionId={}, runId={}", requestId, sessionId, runId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to get run");
        }
    }

    /**
     * 获取 Run 的所有步骤
     * GET /api/v1/sessions/{sessionId}/runs/{runId}/steps
     */
    @GetMapping("/{sessionId}/runs/{runId}/steps")
    public ResponseEntity<List<StepResponse>> getRunSteps(
            @PathVariable UUID sessionId,
            @PathVariable UUID runId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.debug("Get run steps request: requestId={}, sessionId={}, runId={}", requestId, sessionId, runId);

        try {
            List<StepResponse> response = sessionService.getRunSteps(sessionId, runId);
            return ResponseEntity.ok(response);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Get run steps error: requestId={}, sessionId={}, runId={}", requestId, sessionId, runId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to get run steps");
        }
    }

    /**
     * 取消正在执行的 Run
     * POST /api/v1/sessions/{sessionId}/runs/{runId}/cancel
     */
    @PostMapping("/{sessionId}/runs/{runId}/cancel")
    @AuditLog(
        type = "agent.run_cancelled",
        category = "business",
        action = "取消运行",
        resourceType = "agent_run",
        severity = "warn"
    )
    public ResponseEntity<Void> cancelRun(
            @PathVariable UUID sessionId,
            @PathVariable UUID runId) {
        String requestId = RequestIdGenerator.getCurrent();
        log.info("Cancel run request: requestId={}, sessionId={}, runId={}", requestId, sessionId, runId);

        try {
            sessionService.cancelRun(sessionId, runId);
            return ResponseEntity.noContent().build();
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Cancel run error: requestId={}, sessionId={}, runId={}", requestId, sessionId, runId, e);
            throw BusinessException.of(ErrorCode.ERR_SERVICE_UNAVAILABLE, "Failed to cancel run");
        }
    }
}