package com.platform.gateway.service;

import com.platform.gateway.dto.request.CreateSessionRequest;
import com.platform.gateway.dto.request.SessionListRequest;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.RunDetailResponse;
import com.platform.gateway.dto.response.RunResponse;
import com.platform.gateway.dto.response.SessionResponse;
import com.platform.gateway.dto.response.StepResponse;
import com.platform.gateway.entity.AgentRun;
import com.platform.gateway.entity.AgentSession;
import com.platform.gateway.entity.AgentStep;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.AgentRunRepository;
import com.platform.gateway.repository.AgentSessionRepository;
import com.platform.gateway.repository.AgentStepRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

/**
 * 会话服务
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SessionService {

    private final AgentSessionRepository sessionRepository;
    private final AgentRunRepository runRepository;
    private final AgentStepRepository stepRepository;
    private final TenantContextService tenantContextService;

    /**
     * 查询会话列表
     */
    public PageResponse<SessionResponse> listSessions(SessionListRequest request) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        // 构建分页参数
        int pageNumber = request.getPageNumber() != null ? request.getPageNumber() - 1 : 0;
        int pageSize = request.getPageSize() != null ? request.getPageSize() : 20;
        Pageable pageable = PageRequest.of(pageNumber, pageSize, Sort.by(Sort.Direction.DESC, "createdAt"));

        // 查询
        Page<AgentSession> page = sessionRepository.findByTenantAndUserWithFilter(
                tenantId, userId, request.getStatus(), request.getSearch(), pageable);

        // 转换响应
        List<SessionResponse> items = page.getContent().stream()
                .map(this::toResponse)
                .toList();

        return PageResponse.<SessionResponse>builder()
                .items(items)
                .totalCount(page.getTotalElements())
                .pageNumber(request.getPageNumber() != null ? request.getPageNumber() : 1)
                .totalPages(page.getTotalPages())
                .hasNext(page.hasNext())
                .build();
    }

    /**
     * 获取单个会话
     */
    public SessionResponse getSession(UUID sessionId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        AgentSession session = sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        return toResponse(session);
    }

    /**
     * 创建会话
     */
    @Transactional
    public SessionResponse createSession(CreateSessionRequest request) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        AgentSession session = AgentSession.builder()
                .tenantId(tenantId)
                .userId(userId)
                .sessionType(request.getSessionType())
                .title(request.getTitle())
                .status("active")
                .build();

        session = sessionRepository.save(session);

        log.info("Session created: sessionId={}, tenantId={}, userId={}, type={}",
                session.getId(), tenantId, userId, request.getSessionType());

        return toResponse(session);
    }

    /**
     * 删除会话
     */
    @Transactional
    public void deleteSession(UUID sessionId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        AgentSession session = sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        sessionRepository.delete(session);

        log.info("Session deleted: sessionId={}, tenantId={}, userId={}", sessionId, tenantId, userId);
    }

    /**
     * 归档会话
     */
    @Transactional
    public SessionResponse archiveSession(UUID sessionId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        AgentSession session = sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        if ("archived".equals(session.getStatus())) {
            throw new BusinessException(ErrorCode.ERR_SESSION_ARCHIVED, "会话已归档");
        }

        session.setStatus("archived");
        session = sessionRepository.save(session);

        log.info("Session archived: sessionId={}, tenantId={}, userId={}", sessionId, tenantId, userId);

        return toResponse(session);
    }

    /**
     * 取消归档会话
     */
    @Transactional
    public SessionResponse unarchiveSession(UUID sessionId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        AgentSession session = sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        session.setStatus("active");
        session = sessionRepository.save(session);

        log.info("Session unarchived: sessionId={}, tenantId={}, userId={}", sessionId, tenantId, userId);

        return toResponse(session);
    }

    /**
     * 更新会话标题
     */
    @Transactional
    public SessionResponse updateTitle(UUID sessionId, String title) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        AgentSession session = sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        session.setTitle(title);
        session = sessionRepository.save(session);

        log.info("Session title updated: sessionId={}, tenantId={}, userId={}", sessionId, tenantId, userId);

        return toResponse(session);
    }

    /**
     * 实体转响应DTO
     */
    private SessionResponse toResponse(AgentSession session) {
        return SessionResponse.builder()
                .id(session.getId())
                .tenantId(session.getTenantId())
                .userId(session.getUserId())
                .sessionType(session.getSessionType())
                .title(session.getTitle())
                .status(session.getStatus())
                .createdAt(session.getCreatedAt())
                .updatedAt(session.getUpdatedAt())
                .build();
    }

    // ==================== Run 相关方法 ====================

    /**
     * 获取会话的所有 Run
     */
    public PageResponse<RunResponse> getSessionRuns(UUID sessionId, Integer pageNumber, Integer pageSize) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        // 验证会话存在且属于当前用户
        sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        // 构建分页参数
        int page = pageNumber != null ? pageNumber - 1 : 0;
        int size = pageSize != null ? pageSize : 20;
        Pageable pageable = PageRequest.of(page, size, Sort.by(Sort.Direction.DESC, "startedAt"));

        // 查询 Run 列表
        Page<AgentRun> runPage = runRepository.findByTenantIdAndSessionId(tenantId, sessionId, pageable);

        // 转换响应
        List<RunResponse> items = runPage.getContent().stream()
                .map(this::toRunResponse)
                .toList();

        return PageResponse.<RunResponse>builder()
                .items(items)
                .totalCount(runPage.getTotalElements())
                .pageNumber(pageNumber != null ? pageNumber : 1)
                .totalPages(runPage.getTotalPages())
                .hasNext(runPage.hasNext())
                .build();
    }

    /**
     * 获取单个 Run 详情
     */
    public RunDetailResponse getRun(UUID sessionId, UUID runId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        // 验证会话存在且属于当前用户
        sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        // 查询 Run
        AgentRun run = runRepository.findByIdAndTenantId(runId, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_NOT_FOUND, "运行不存在"));

        // 验证 Run 属于该 Session
        if (!run.getSessionId().equals(sessionId)) {
            throw new BusinessException(ErrorCode.ERR_NOT_FOUND, "运行不存在");
        }

        // 获取步骤数
        long stepCount = stepRepository.countByRunId(runId);

        return toRunDetailResponse(run, (int) stepCount, null);
    }

    /**
     * 获取 Run 的所有步骤
     */
    public List<StepResponse> getRunSteps(UUID sessionId, UUID runId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        // 验证会话存在且属于当前用户
        sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        // 查询 Run
        AgentRun run = runRepository.findByIdAndTenantId(runId, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_NOT_FOUND, "运行不存在"));

        // 验证 Run 属于该 Session
        if (!run.getSessionId().equals(sessionId)) {
            throw new BusinessException(ErrorCode.ERR_NOT_FOUND, "运行不存在");
        }

        // 查询步骤列表
        List<AgentStep> steps = stepRepository.findByRunIdOrderByStepOrderAsc(runId);

        return steps.stream()
                .map(this::toStepResponse)
                .toList();
    }

    /**
     * 取消正在执行的 Run
     */
    @Transactional
    public void cancelRun(UUID sessionId, UUID runId) {
        String tenantId = tenantContextService.getCurrentTenantId();
        String userId = tenantContextService.getCurrentUserId();

        // 验证会话存在且属于当前用户
        sessionRepository.findByIdAndTenantIdAndUserId(sessionId, tenantId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_SESSION_NOT_FOUND, "会话不存在"));

        // 查询 Run
        AgentRun run = runRepository.findByIdAndTenantId(runId, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_NOT_FOUND, "运行不存在"));

        // 验证 Run 属于该 Session
        if (!run.getSessionId().equals(sessionId)) {
            throw new BusinessException(ErrorCode.ERR_NOT_FOUND, "运行不存在");
        }

        // 检查状态是否为 running
        if (!"running".equals(run.getStatus())) {
            throw new BusinessException(ErrorCode.ERR_INVALID_REQUEST,
                    "只能取消运行中的任务，当前状态: " + run.getStatus());
        }

        // 更新状态为 cancelled
        run.setStatus("cancelled");
        run.setCompletedAt(java.time.Instant.now());
        runRepository.save(run);

        log.info("Run cancelled: runId={}, sessionId={}, tenantId={}, userId={}", runId, sessionId, tenantId, userId);
    }

    /**
     * Run 实体转响应 DTO
     */
    private RunResponse toRunResponse(AgentRun run) {
        return RunResponse.builder()
                .id(run.getId())
                .runNumber(run.getRunNumber())
                .status(run.getStatus())
                .inputMessage(run.getInputMessage())
                .outputMessage(run.getOutputMessage())
                .modelUsed(run.getModelUsed())
                .totalTokens(run.getTotalTokens())
                .totalCostUsd(run.getTotalCostUsd())
                .durationMs(run.getDurationMs())
                .startedAt(run.getStartedAt())
                .completedAt(run.getCompletedAt())
                .errorMessage(run.getErrorMessage())
                .build();
    }

    /**
     * Run 实体转详情响应 DTO
     */
    private RunDetailResponse toRunDetailResponse(AgentRun run, int stepCount, List<StepResponse> steps) {
        return RunDetailResponse.builder()
                .id(run.getId())
                .sessionId(run.getSessionId())
                .runNumber(run.getRunNumber())
                .status(run.getStatus())
                .inputMessage(run.getInputMessage())
                .outputMessage(run.getOutputMessage())
                .modelUsed(run.getModelUsed())
                .totalTokens(run.getTotalTokens())
                .totalCostUsd(run.getTotalCostUsd())
                .durationMs(run.getDurationMs())
                .startedAt(run.getStartedAt())
                .completedAt(run.getCompletedAt())
                .errorMessage(run.getErrorMessage())
                .errorCode(run.getErrorCode())
                .stepCount(stepCount)
                .steps(steps)
                .build();
    }

    /**
     * Step 实体转响应 DTO
     */
    private StepResponse toStepResponse(AgentStep step) {
        return StepResponse.builder()
                .id(step.getId())
                .stepOrder(step.getStepOrder())
                .stepType(step.getStepType())
                .content(step.getContent())
                .toolName(step.getToolName())
                .toolInput(step.getToolInput())
                .toolOutput(step.getToolOutput())
                .tokenCount(step.getTokenCount())
                .durationMs(step.getDurationMs())
                .createdAt(step.getCreatedAt())
                .build();
    }
}