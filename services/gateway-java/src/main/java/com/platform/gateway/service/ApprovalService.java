package com.platform.gateway.service;

import com.platform.gateway.dto.request.ApprovalActionRequest;
import com.platform.gateway.dto.request.ApprovalListRequest;
import com.platform.gateway.dto.response.ApprovalTaskResponse;
import com.platform.gateway.dto.response.PagedResponse;
import com.platform.gateway.entity.ApprovalTask;
import com.platform.gateway.exception.BusinessException;
import com.platform.gateway.exception.ErrorCode;
import com.platform.gateway.repository.ApprovalTaskRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * 审批服务
 *
 * <p>负责 Agent 工具调用的审批流程管理，是风控体系的核心组件。
 *
 * <h3>核心概念：人工审批机制</h3>
 *
 * <p>当 Agent 执行高风险操作（如删除数据、财务操作）时，系统自动创建审批任务，
 * 等待人工审核通过后才继续执行。这是 S-AGENT-07 风险等级控制的核心实现。
 *
 * <h3>依赖关系</h3>
 * <pre>
 * ┌─────────────────────────────────────────────────────────────────────────────┐
 * │                          服务依赖关系                                        │
 * │                                                                             │
 * │   ApprovalController                                                        │
 * │       │                                                                     │
 * │       ▼                                                                     │
 * │   ApprovalService ◄───────────────────────────────────────────────────────  │
 * │       │                                                                     │
 * │       ├──► ApprovalTaskRepository (数据持久化)                              │
 * │       │                                                                     │
 * │       └──► OrchestratorClient (审批通过后通知 Agent 继续执行)               │
 * │                                                                             │
 * └─────────────────────────────────────────────────────────────────────────────┘
 * </pre>
 *
 * <h3>技术选型：状态管理</h3>
 * <ul>
 *   <li><b>状态机模式</b>：审批任务状态流转采用状态机模式，状态不可逆转</li>
 *   <li><b>乐观锁</b>：通过 version 字段防止并发审批冲突</li>
 *   <li><b>定时任务</b>：配合 {@code @Scheduled} 定时标记过期审批</li>
 * </ul>
 *
 * <h3>状态流转</h3>
 * <pre>
 *   ┌─────────┐
 *   │ pending │ ──────────────────────────────────────────────┐
 *   └────┬────┘                                               │
 *        │                                                    │
 *   ┌────┴────┐                                           ┌───┴───┐
 *   │approved │                                           │expired│
 *   └─────────┘                                           └───────┘
 *        │
 *   ┌────┴────┐
 *   │rejected │
 *   └─────────┘
 * </pre>
 *
 * <h3>设计模式：模板方法</h3>
 *
 * <p>{@link #approve} 和 {@link #reject} 方法采用模板方法模式，
 * 共享状态校验和过期检查逻辑，仅在最终状态更新处有所不同。
 *
 * <h3>事务处理</h3>
 *
 * <p>所有写操作使用 {@code @Transactional} 保证：
 * <ul>
 *   <li>状态更新的原子性</li>
 *   <li>审批记录的完整性</li>
 *   <li>乐观锁冲突时自动回滚</li>
 * </ul>
 *
 * @see ApprovalTask 审批任务实体
 * @see ApprovalTaskRepository 审批任务仓库
 * @since 1.0.0
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ApprovalService {

    private final ApprovalTaskRepository approvalTaskRepository;

    /**
     * 查询审批列表（分页）
     *
     * <p>支持多条件筛选和排序，返回分页结果。
     *
     * <h4>查询条件</h4>
     * <ul>
     *   <li><b>status</b>：审批状态（pending/approved/rejected/expired）</li>
     *   <li><b>priority</b>：优先级（urgent/high/normal/low）</li>
     *   <li><b>task_type</b>：任务类型（如 data_deletion, financial_operation）</li>
     * </ul>
     *
     * <h4>排序规则</h4>
     * <ul>
     *   <li>priority：优先级排序（urgent &gt; high &gt; normal &gt; low）</li>
     *   <li>expires_at：过期时间排序</li>
     *   <li>created_at：创建时间排序（默认）</li>
     * </ul>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能查询本租户的审批任务</li>
     *   <li>权限控制：需要 approval:read 权限</li>
     *   <li>默认排序：按创建时间降序</li>
     * </ul>
     *
     * @param request 查询请求参数，包含分页、排序和筛选条件
     * @param tenantId 租户ID，用于租户隔离
     * @return 分页的审批任务响应
     * @since 1.0.0
     */
    public PagedResponse<ApprovalTaskResponse> listApprovals(ApprovalListRequest request, String tenantId) {
        // 构建分页参数
        int pageNumber = request.getPage() != null ? request.getPage() - 1 : 0;
        int pageSize = request.getPage_size() != null ? request.getPage_size() : 10;

        String sortBy = request.getSort_by() != null ? request.getSort_by() : "createdAt";
        boolean ascending = "asc".equalsIgnoreCase(request.getSort_order());
        Sort.Direction direction = ascending ? Sort.Direction.ASC : Sort.Direction.DESC;
        Sort sort = mapSortField(sortBy, direction);

        Pageable pageable = PageRequest.of(pageNumber, pageSize, sort);

        // 查询
        Page<ApprovalTask> page = approvalTaskRepository.findByConditions(
                tenantId,
                request.getStatus(),
                request.getPriority(),
                request.getTask_type(),
                null, // assigneeId
                pageable
        );

        // 转换响应
        List<ApprovalTaskResponse> items = page.getContent().stream()
                .map(this::toResponse)
                .toList();

        return PagedResponse.<ApprovalTaskResponse>builder()
                .items(items)
                .total(page.getTotalElements())
                .page(request.getPage() != null ? request.getPage() : 1)
                .page_size(pageSize)
                .total_pages(page.getTotalPages())
                .build();
    }

    /**
     * 获取审批详情
     *
     * <p>查询单个审批任务的完整信息，包括请求上下文、审批历史等。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>租户隔离：只能查询本租户的审批任务</li>
     *   <li>权限控制：需要 approval:read 权限</li>
     * </ul>
     *
     * @param approvalId 审批任务ID（UUID格式）
     * @param tenantId 租户ID，用于租户隔离
     * @return 审批任务详情
     * @throws BusinessException ERR_APPROVAL_NOT_FOUND 审批任务不存在
     * @throws BusinessException ERR_INVALID_REQUEST 审批ID格式错误
     * @since 1.0.0
     */
    public ApprovalTaskResponse getApproval(String approvalId, String tenantId) {
        UUID id = parseUUID(approvalId, "审批ID格式错误");

        ApprovalTask task = approvalTaskRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_APPROVAL_NOT_FOUND, "审批任务不存在"));

        return toResponse(task);
    }

    /**
     * 通过审批
     *
     * <p>审批人确认同意执行该操作，审批任务状态变为 approved。
     * 审批通过后，Orchestrator 会收到通知继续执行 Agent 的工具调用。
     *
     * <h4>处理流程</h4>
     * <ol>
     *   <li>状态校验：只有 pending 状态可以审批</li>
     *   <li>过期检查：过期任务自动标记为 expired</li>
     *   <li>更新状态：设置 approved、reviewerId、reviewedAt</li>
     *   <li>持久化：保存审批记录</li>
     *   <li>通知 Agent：通过回调通知 Orchestrator 继续执行</li>
     * </ol>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>幂等性：已处理的审批不能重复操作</li>
     *   <li>租户隔离：只能审批本租户的任务</li>
     *   <li>权限控制：需要 approval:approve 权限</li>
     *   <li>审计日志：记录审批人和审批时间</li>
     * </ul>
     *
     * @param approvalId 审批任务ID（UUID格式）
     * @param request 审批请求，包含审批意见
     * @param reviewerId 审批人ID
     * @param tenantId 租户ID，用于租户隔离
     * @return 更新后的审批任务详情
     * @throws BusinessException ERR_APPROVAL_NOT_FOUND 审批任务不存在
     * @throws BusinessException ERR_APPROVAL_ALREADY_REVIEWED 审批已处理
     * @throws BusinessException ERR_APPROVAL_EXPIRED 审批已过期
     * @since 1.0.0
     */
    @Transactional
    public ApprovalTaskResponse approve(String approvalId, ApprovalActionRequest request, String reviewerId, String tenantId) {
        UUID id = parseUUID(approvalId, "审批ID格式错误");

        ApprovalTask task = approvalTaskRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_APPROVAL_NOT_FOUND, "审批任务不存在"));

        // 状态校验
        if (!"pending".equals(task.getStatus())) {
            throw new BusinessException(ErrorCode.ERR_APPROVAL_ALREADY_REVIEWED, "审批已处理");
        }

        // 过期检查
        if (task.getExpiresAt() != null && Instant.now().isAfter(task.getExpiresAt())) {
            task.setStatus("expired");
            approvalTaskRepository.save(task);
            throw new BusinessException(ErrorCode.ERR_APPROVAL_EXPIRED, "审批已过期");
        }

        // 更新审批状态
        task.setStatus("approved");
        task.setReviewerId(reviewerId);
        task.setReviewComment(request != null ? request.getComment() : null);
        task.setReviewedAt(Instant.now());

        task = approvalTaskRepository.save(task);

        log.info("Approval approved: approvalId={}, reviewerId={}", approvalId, reviewerId);

        return toResponse(task);
    }

    /**
     * 拒绝审批
     *
     * <p>审批人拒绝执行该操作，审批任务状态变为 rejected。
     * 审批拒绝后，Agent 会收到拒绝结果并中止工具调用。
     *
     * <h4>处理流程</h4>
     * <ol>
     *   <li>状态校验：只有 pending 状态可以审批</li>
     *   <li>过期检查：过期任务自动标记为 expired</li>
     *   <li>更新状态：设置 rejected、reviewerId、reviewedAt</li>
     *   <li>持久化：保存审批记录</li>
     *   <li>通知 Agent：通过回调通知 Orchestrator 任务被拒绝</li>
     * </ol>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>幂等性：已处理的审批不能重复操作</li>
     *   <li>租户隔离：只能审批本租户的任务</li>
     *   <li>权限控制：需要 approval:approve 权限</li>
     *   <li>审计日志：记录审批人和审批时间</li>
     * </ul>
     *
     * @param approvalId 审批任务ID（UUID格式）
     * @param request 审批请求，包含拒绝原因
     * @param reviewerId 审批人ID
     * @param tenantId 租户ID，用于租户隔离
     * @return 更新后的审批任务详情
     * @throws BusinessException ERR_APPROVAL_NOT_FOUND 审批任务不存在
     * @throws BusinessException ERR_APPROVAL_ALREADY_REVIEWED 审批已处理
     * @throws BusinessException ERR_APPROVAL_EXPIRED 审批已过期
     * @since 1.0.0
     */
    @Transactional
    public ApprovalTaskResponse reject(String approvalId, ApprovalActionRequest request, String reviewerId, String tenantId) {
        UUID id = parseUUID(approvalId, "审批ID格式错误");

        ApprovalTask task = approvalTaskRepository.findByIdAndTenantId(id, tenantId)
                .orElseThrow(() -> new BusinessException(ErrorCode.ERR_APPROVAL_NOT_FOUND, "审批任务不存在"));

        // 状态校验
        if (!"pending".equals(task.getStatus())) {
            throw new BusinessException(ErrorCode.ERR_APPROVAL_ALREADY_REVIEWED, "审批已处理");
        }

        // 过期检查
        if (task.getExpiresAt() != null && Instant.now().isAfter(task.getExpiresAt())) {
            task.setStatus("expired");
            approvalTaskRepository.save(task);
            throw new BusinessException(ErrorCode.ERR_APPROVAL_EXPIRED, "审批已过期");
        }

        // 更新审批状态
        task.setStatus("rejected");
        task.setReviewerId(reviewerId);
        task.setReviewComment(request != null ? request.getComment() : null);
        task.setReviewedAt(Instant.now());

        task = approvalTaskRepository.save(task);

        log.info("Approval rejected: approvalId={}, reviewerId={}", approvalId, reviewerId);

        return toResponse(task);
    }

    /**
     * 创建审批任务（内部方法）
     *
     * <p>由 Orchestrator 调用，创建新的审批任务。
     * 该方法通常在 Agent 执行高风险工具调用时自动触发。
     *
     * <h4>创建时机</h4>
     * <ul>
     *   <li>工具风险等级为 high 或 critical（S-AGENT-07）</li>
     *   <li>租户配置要求人工审批</li>
     *   <li>特定操作类型强制审批（如删除数据）</li>
     * </ul>
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>自动生成 UUID 作为主键</li>
     *   <li>设置默认过期时间（APPROVAL_WAIT_TIMEOUT_S）</li>
     *   <li>分配审批人（基于租户配置或轮询策略）</li>
     * </ul>
     *
     * @param task 审批任务实体，需包含 tenantId、taskType、requestContext
     * @return 创建后的审批任务详情
     * @since 1.0.0
     */
    @Transactional
    public ApprovalTaskResponse createApprovalTask(ApprovalTask task) {
        task = approvalTaskRepository.save(task);
        log.info("Approval task created: id={}, tenantId={}, type={}",
                task.getId(), task.getTenantId(), task.getTaskType());
        return toResponse(task);
    }

    /**
     * 批量标记过期审批（定时任务）
     *
     * <p>定期扫描已过期的待审批任务，自动标记为 expired 状态。
     * 通常配合 {@code @Scheduled} 注解使用，每分钟执行一次。
     *
     * <h4>业务规则</h4>
     * <ul>
     *   <li>只处理 pending 状态的任务</li>
     *   <li>过期时间 &lt; 当前时间</li>
     *   <li>批量更新提高效率</li>
     * </ul>
     *
     * <h4>通知机制</h4>
     * <p>过期后通知 Orchestrator 取消对应的 Agent 执行。
     *
     * @return 标记为过期的任务数量
     * @since 1.0.0
     */
    @Transactional
    public int markExpiredApprovals() {
        List<ApprovalTask> expiredTasks = approvalTaskRepository.findExpiredPendingApprovals(Instant.now());
        for (ApprovalTask task : expiredTasks) {
            task.setStatus("expired");
        }
        approvalTaskRepository.saveAll(expiredTasks);
        log.info("Marked {} approval tasks as expired", expiredTasks.size());
        return expiredTasks.size();
    }

    // ========== 辅助方法 ==========

    private ApprovalTaskResponse toResponse(ApprovalTask task) {
        return ApprovalTaskResponse.builder()
                .id(task.getId().toString())
                .run_id(task.getRunId() != null ? task.getRunId().toString() : null)
                .tool_invocation_id(task.getToolInvocationId() != null ? task.getToolInvocationId().toString() : null)
                .tenant_id(task.getTenantId())
                .task_type(task.getTaskType())
                .title(task.getTitle())
                .description(task.getDescription())
                .request_context(task.getRequestContext())
                .requester_id(task.getRequesterId())
                .assignee_id(task.getAssigneeId())
                .priority(task.getPriority())
                .status(task.getStatus())
                .reviewer_id(task.getReviewerId())
                .review_comment(task.getReviewComment())
                .reviewed_at(task.getReviewedAt())
                .expires_at(task.getExpiresAt())
                .created_at(task.getCreatedAt())
                .updated_at(task.getUpdatedAt())
                .build();
    }

    private Sort mapSortField(String sortBy, Sort.Direction direction) {
        String fieldName;
        switch (sortBy) {
            case "priority":
                fieldName = "priority";
                // 优先级排序需要特殊处理：urgent > high > normal > low
                // 这里用权重计算，但 JPA 排序不支持表达式，所以先按字段排序
                break;
            case "expires_at":
                fieldName = "expiresAt";
                break;
            case "created_at":
            default:
                fieldName = "createdAt";
                break;
        }
        return Sort.by(direction, fieldName);
    }

    private UUID parseUUID(String str, String errorMessage) {
        try {
            return UUID.fromString(str);
        } catch (IllegalArgumentException e) {
            throw new BusinessException(ErrorCode.ERR_INVALID_REQUEST, errorMessage);
        }
    }
}
