# Agent Platform 运行原理（生产落地增强）

> **版本**：v1.0 | **更新**：2026-06-16
> 本文档讲解 P0/P1 生产落地增强后，平台核心链路的运行原理，帮助快速理解
> "请求如何流转、各服务如何协作、关键机制如何生效"。通用规则见 CLAUDE.md，
> 安全规范见 [03-security-specification](03-security-specification.md)。

---

## 1. 端到端请求流转总览

```
前端(React useChat/useSSE)
        │  POST /api/v1/chat/completions  (SSE, stream=true)
        ▼
Gateway(Java) ── 鉴权/CORS/限流 ──► ChatController(SseEmitter)
        │  gRPC StreamChatCompletion
        ▼
Orchestrator(Python) ── LangGraph 状态机 ──► thinking → [risk_check] → tool_call
        │                                          │            │
        │  chat_completion(gRPC)                   │            │ gRPC executeTool
        ▼                                          │            ▼
Model Gateway(Python) ── 路由/failover ──►     RAG?         Tool Bus(Java)
   Qwen / DeepSeek / GLM                      Knowledge      ToolRiskGate → 真实工具
                                              (pgvector)     高风险→pending_approval
                                                                  │
                                                                  ▼
                                                            Governance(Java)
                                                       风险评估/审批人分配/超时拒绝
```

---

## 2. 流式输出链路（P0-1）

### 设计取舍：答案级流式
- Orchestrator 的 `thinking` 节点使用自定义 `ModelGatewayClient`（非 LangChain
  ChatModel），LangGraph 无法自动产出 token 级事件。
- 因此采用**答案级流式**：完整执行 Agent 图（保留工具/风控/审批逻辑），
  图执行完成后将最终答案按 `STREAM_CHUNK_SIZE`（24 字符）切块逐块下发。
- 未来若将 thinking 节点接入 LangChain ChatModel 的 `astream`，可平滑升级为
  token 级流式，对外协议（`ChatStreamChunk`）不变。

### 链路与契约
| 段 | 协议 | 关键字段 |
|---|---|---|
| 前端 ↔ Gateway | SSE (`text/event-stream`) | `delta_content`、`is_final`、`finish_reason` |
| Gateway ↔ Orchestrator | gRPC server-streaming | `ChatStreamChunk{delta, chunk_index, finish_reason, error}` |
| Orchestrator HTTP（自用） | SSE | `data: {delta, finish_reason}` + `data: [DONE]` |

- 关键实现：`OrchestratorClient.streamChatRequest`（逐块回调）→ `ChatController`
  转 SSE；`OrchestratorServiceServicer.StreamChatCompletion`（切块）。
- 审批中断时下发 `finish_reason=pending_approval` + `approval_id`；错误下发
  `finish_reason=error` + `ErrorDetail`。

---

## 3. 审批闭环（P0-3）

五层鉴权第 5 层（风险等级）在执行链路上的落地：

```
thinking → risk_check(编排层本地评估) ─┬─ 低风险 → tool_call
                                       └─ 高风险 → approval_wait(interrupt 暂停)

tool_call → Tool Bus ── ToolRiskGate(执行侧强制) ─┬─ 低风险 → 真实执行
                                                  └─ 高风险 → pending_approval
                                                                    │
Governance ── createApprovalTask(审批人分配) → 通知 → 人工审批 ──────┘
           └─ autoRejectExpiredApprovals(@Scheduled, 超时自动拒绝)
```

- **双层防御**：编排层 `risk_check` 先评估；Tool Bus 的 `ToolRiskGate` 在执行
  前再次强制（即便编排层判低风险，工具定义 `requiresApproval`/高风险关键词/
  金额阈值/敏感字段命中也会拦截），返回 `pending_approval`。
- **暂停/恢复**：LangGraph `interrupt_before=["approval_wait"]` 配合 Redis
  checkpoint 持久化；审批结果经 Kafka 回调恢复执行（approved→tool_call，
  rejected→final_answer）。
- **超时治理**：`ApprovalService.autoRejectExpiredApprovals` 每分钟扫描，过期
  pending 任务自动置 rejected 并发布结果事件，避免请求永久挂起
  （`APPROVAL_WAIT_TIMEOUT_S=7200`）。

---

## 4. 工具执行（P0-4）

- `ToolExecutor` 接口统一 Mock/Real 两种实现，由 Spring Profile 注入：
  - `dev/local/test` → `MockToolExecutor`（预定义响应，便于测试）
  - `prod` → `RealToolExecutor`（分发到 `RealTool` Bean，如 PaymentTool）
- **虚拟线程**：`RealToolExecutor` 在 Java 21 虚拟线程上执行每次工具调用，
  配合 `TOOL_TIMEOUT_SECONDS=15` 超时控制（S-AGENT-08）。
- 两种实现都先经过 `ToolRiskGate`，确保审批闭环在开发环境也可验证。

---

## 5. 多 LLM Provider 与故障转移（P0-5）

- Model Gateway 通过 `BaseLLMProvider` 抽象统一各厂商；已接入 Qwen、DeepSeek、
  GLM（API Key 走环境变量，未配置则跳过注册）。
- `ModelRouter.route` 决策优先级：用户指定模型 → 租户主模型 → fallback 列表，
  每步检查熔断器可用性；全部不可用抛 `AllProvidersDownError`。
- 多 Provider 注册后，某 Provider 熔断时自动故障转移到备用，避免单点全挂。

---

## 6. CORS 统一（P0-2）

- 删除历史上三处冲突配置（SimpleCorsFilter/WebCorsConfig/CorsFilterConfig），
  收敛到 `SecurityConfig` 单一 `CorsConfigurationSource`。
- 白名单走配置 `app.cors.allowed-origins`；**生产 profile 默认空**（拒绝所有
  跨域），必须通过 `CORS_ALLOWED_ORIGINS` 显式指定可信域名，杜绝通配符泄露。

---

## 7. 分布式限流（P1-6）

- `BucketManager` 接口统一本地/分布式实现，由 `rate-limit.distributed.enabled`
  切换：
  - `false`（默认/单实例）→ `LocalBucketManager`（ConcurrentHashMap）
  - `true`（生产/多副本）→ `RedisBucketManager`（bucket4j-redis + Lettuce）
- 多副本部署下配额经 Redis 全局共享，避免"每实例独立配额"导致的限流失效。
- 双维度：用户级 RPM + 租户级 TPM。

---

## 8. RAG 接入编排（P1-9）

```
thinking ──(知识型问题 & 未检索)──► rag_retrieve ──► thinking(带文档上下文)
```

- `thinking` 节点的 RAG 门：`enable_rag` 且 `step_count==0` 且未检索且命中知识
  关键词时，路由到 `rag_retrieve`。
- `rag_retrieve` 调用 Knowledge 服务（pgvector 检索），结果写入 `retrieved_docs`
  并返回 thinking。**双重防循环**：`step_count==0` + `retrieved_docs` 非空守卫。
- 检索文档作为 system 上下文注入 `_build_messages`，供模型据此作答。

---

## 9. 上下文与摘要（P1-10）

- `ContextManager.truncate`（同步）：滑动窗口 + 提取式摘要（复用
  `SummaryGenerator._generate_extractive`）。
- `ContextManager.truncate_async`（异步）：旧消息走 LLM 高质量摘要
  （`SummaryGenerator.generate`，失败回退提取式）。

---

## 10. 响应缓存与内容过滤（P1-13）

- **内容过滤**（前置）：`ContentFilter` 本地敏感词预检，命中抛
  `ModelContentFilteredError`（HTTP 400），不发往 Provider。
- **响应缓存**：`ResponseCache`（Redis）对低温度（≤0.3）非流式请求按
  model+messages+参数哈希缓存，命中直接返回，降低成本与延迟。

---

## 11. 数据 Schema 与迁移（P1-7 / P1-8）

| 服务 | 迁移工具 | 关键对象 |
|---|---|---|
| gateway-java | Flyway | 业务表 + `audit_event` 防删改触发器（V1.0.8，G-SEC-03） |
| knowledge-python | Alembic（原生 SQL） | pgvector 扩展 + `knowledge_document`/`knowledge_chunk` |
| orchestrator-python | Alembic（原生 SQL） | pgvector 扩展 + `agent_memory`（长时记忆） |

- 审计不可删改：`audit_event` 的 BEFORE UPDATE/DELETE/TRUNCATE 触发器在数据库
  层阻断任何篡改。
- Alembic 注意：`alembic.ini` 被 alembic 以 OS locale 编码读取，GBK 区域
  Windows 下须保持 ASCII；中文文档在 `env.py` 与迁移脚本中（按 UTF-8 读取）。

---

## 12. 部署加固（P1-11 / P1-12）

- 7 个服务均有 Dockerfile（多阶段、非 root、healthcheck）；补齐
  model-gateway 的 `/health`、`/ready` 探针与 Dockerfile。
- K8s base 新增生产加固清单：
  - `pdb.yaml`：PodDisruptionBudget（滚动更新/驱逐保最小可用）
  - `networkpolicy.yaml`：East-West 零信任，默认拒绝 + 按拓扑放行
  - `rbac.yaml`：每服务独立 ServiceAccount + 禁用 token 自动挂载
  - `secret-template.yaml`：Secret 占位模板（生产用外部 Secret 管理器覆盖）
```
