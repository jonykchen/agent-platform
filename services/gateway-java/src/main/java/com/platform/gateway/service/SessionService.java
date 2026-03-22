package com.platform.gateway.service;

import com.platform.gateway.dto.request.CreateSessionRequest;
import com.platform.gateway.dto.request.SessionListRequest;
import com.platform.gateway.dto.response.PageResponse;
import com.platform.gateway.dto.response.SessionResponse;
import com.platform.gateway.entity.AgentSession;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.AgentSessionRepository;
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
}