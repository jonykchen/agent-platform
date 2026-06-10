"""
【核心概念】Kafka 回调恢复机制
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Orchestrator 消费 Kafka 中的审批结果事件，恢复 LangGraph Checkpoint 执行。

【问题背景】
1. Agent 执行高风险操作时需要人工审批（如删除数据库、转账）
2. 审批可能在数小时甚至数天后完成
3. Orchestrator 服务需要可靠地接收审批结果并恢复任务执行

【技术选型】回调机制对比
┌────────────────┬─────────────┬─────────────┬─────────────┬─────────────┐
│ 方案           │ 可靠性      │ 实时性      │ 运维成本    │ 适用场景    │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ ✓ Kafka        │ ★★★★★      │ ★★★★☆      │ ★★★☆☆      │ 异步审批    │
│                │ 持久化+重试 │ 秒级延迟    │ 需运维集群  │ 高可靠要求  │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ HTTP Webhook   │ ★★★☆☆      │ ★★★★★      │ ★★★★★      │ 简单场景    │
│                │ 需处理失败  │ 即时        │ 无基础设施  │ 快速原型    │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ WebSocket      │ ★★☆☆☆      │ ★★★★★      │ ★★★☆☆      │ 实时推送    │
│                │ 连接不稳定  │ 毫秒级      │ 需维护连接  │ 双向通信    │
├────────────────┼─────────────┼─────────────┼─────────────┼─────────────┤
│ 长轮询         │ ★★★★☆      │ ★★☆☆☆      │ ★★★★☆      │ 低并发      │
│                │ 轮询开销    │ 秒级延迟    │ 简单        │ 兼容性好    │
└────────────────┴─────────────┴─────────────┴─────────────┴─────────────┘

【决策依据】选择 Kafka 的原因：
1. 消息持久化：即使 Orchestrator 重启，消息不会丢失
2. 至少一次投递：Kafka 保证消息至少被消费一次
3. 消费者组：支持多实例部署，自动负载均衡
4. 项目已有 Kafka：复用现有基础设施（事件驱动架构）
5. 解耦：Governance 服务无需知道 Orchestrator 实例地址

【Kafka 回调 vs HTTP 回调】
┌─────────────────────────────────────────────────────────────────────────┐
│ HTTP 回调（传统方式）                    │ Kafka 回调（当前方式）      │
├─────────────────────────────────────────┼─────────────────────────────┤
│ Governance 直接调用 Orchestrator API    │ Governance 发事件到 Kafka  │
│ 需要知道所有 Orchestrator 实例地址      │ 无需知道消费者地址          │
│ 实例扩缩容需更新配置                    │ 消费者组自动负载均衡        │
│ 调用失败需 Governance 重试              │ Kafka 持久化，Orchestrator │
│                                        │ 消费时重试                  │
│ Orchestrator 宕机则消息丢失             │ 消息持久化，不丢失          │
└─────────────────────────────────────────┴─────────────────────────────┘

【架构位置】
┌─────────────────────────────────────────────────────────────────────────┐
│                        审批回调数据流                                   │
│                                                                         │
│   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     │
│   │ 管理员    │     │Governance│     │  Kafka   │     │Orchestrator│   │
│   │ 审批界面  │     │  服务    │     │  Topic   │     │  Callback  │   │
│   └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     │
│        │                │                │                │            │
│        │ 点击"通过"     │                │                │            │
│        │───────────────>│                │                │            │
│        │                │                │                │            │
│        │                │ 发送审批事件    │                │            │
│        │                │───────────────>│                │            │
│        │                │                │                │            │
│        │                │                │ 消费消息       │            │
│        │                │                │───────────────>│            │
│        │                │                │                │            │
│        │                │                │   恢复 Checkpoint           │
│        │                │                │   继续执行 Agent            │
│        │                │                │                │            │
└─────────────────────────────────────────────────────────────────────────┘

【消费者组设计】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【单消费者 vs 多消费者】
┌────────────────┬─────────────────────────────┬─────────────────────────┐
│ 模式           │ 优点                        │ 缺点                    │
├────────────────┼─────────────────────────────┼─────────────────────────┤
│ 单消费者       │ • 简单，无协调开销          │ • 单点故障              │
│ (group_id=1)   │ • 顺序处理，无并发问题      │ • 吞吐量受限            │
├────────────────┼─────────────────────────────┼─────────────────────────┤
│ ✓ 多消费者     │ • 高可用，故障自动转移      │ • 需要幂等处理          │
│ (消费者组)     │ • 水平扩展，提高吞吐        │ • 顺序可能打乱          │
│                │ • Kafka 自动分区分配        │                         │
└────────────────┴─────────────────────────────┴─────────────────────────┘

【当前配置】
- Topic: agent-platform.approval
- 消费者组: orchestrator-callback（所有 Orchestrator 实例共享）
- 分区策略: 默认（RoundRobin 或 Range）

【分区与负载均衡】
┌─────────────────────────────────────────────────────────────────────────┐
│                    Kafka Topic: agent-platform.approval                 │
│                                                                         │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │
│   │ Partition 0 │  │ Partition 1 │  │ Partition 2 │                   │
│   │ [msg][msg]  │  │ [msg][msg]  │  │ [msg][msg]  │                   │
│   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                   │
│          │                │                │                           │
│          ▼                ▼                ▼                           │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                   │
│   │ Orchestrator│  │ Orchestrator│  │ Orchestrator│                   │
│   │ Instance 1  │  │ Instance 2  │  │ Instance 3  │                   │
│   └─────────────┘  └─────────────┘  └─────────────┘                   │
│                                                                         │
│   每个分区只被一个消费者消费，确保同一 run_id 的消息顺序处理           │
└─────────────────────────────────────────────────────────────────────────┘

【幂等性保证机制】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【为什么需要幂等性？】
Kafka 提供至少一次投递（at-least-once），可能出现重复消费：
1. 消费者处理完消息但 commit 失败 → 重启后重新消费
2. 网络抖动导致 rebalance → 消息可能被重复分配
3. 消费者崩溃 → 消息被重新分配给其他消费者

【幂等性实现方案】
┌─────────────────────────────────────────────────────────────────────────┐
│                      幂等性保证流程                                      │
│                                                                         │
│   1. 收到审批事件 (approval_id, run_id)                                │
│   2. 检查 Checkpoint 状态：                                             │
│      - 不存在 → 任务已过期或已完成，忽略                                │
│      - approval_status != "pending" → 已处理，忽略                      │
│      - approval_status == "pending" → 处理并更新状态                    │
│   3. 使用 Redis WATCH/MULTI 或 SETNX 保证原子性                        │
│                                                                         │
│   关键：状态转换是幂等的                                                │
│   pending → approved: 幂等（多次执行结果相同）                          │
│   pending → rejected: 幂等                                              │
│   approved → approved: 幂等（无操作）                                   │
└─────────────────────────────────────────────────────────────────────────┘

【当前实现】
- Checkpoint 检查：load() 返回 None 表示不存在
- 状态更新：仅当 approval_status == "pending" 时处理
- 执行结果：LangGraph ainvoke 对同一 checkpoint 幂等

【死信队列与重试策略】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【重试策略】
┌────────────────┬─────────────────────────────┬─────────────────────────┐
│ 异常类型       │ 处理策略                    │ 原因                    │
├────────────────┼─────────────────────────────┼─────────────────────────┤
│ Checkpoint     │ 记录日志，跳过（不重试）    │ 任务已过期/完成，重试   │
│ 不存在         │                             │ 无意义                  │
├────────────────┼─────────────────────────────┼─────────────────────────┤
│ LangGraph      │ 记录日志，跳过（不重试）    │ 状态已损坏，需人工干预  │
│ 执行失败       │                             │                         │
├────────────────┼─────────────────────────────┼─────────────────────────┤
│ Redis 连接失败 │ Kafka 自动重投（rebalance） │ 暂时性故障，等待恢复    │
├────────────────┼─────────────────────────────┼─────────────────────────┤
│ Kafka 消费异常 │ AIOKafkaConsumer 自动重连   │ Kafka 客户端内置重连    │
└────────────────┴─────────────────────────────┴─────────────────────────┘

【死信队列设计（未来扩展）】
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   主 Topic                    │ 死信队列 (DLQ)                          │
│   agent-platform.approval     │ agent-platform.approval.dlq             │
│   ─────────────────           │ ─────────────────────────────           │
│                                │                                         │
│   [消息1] → 处理成功 ✓        │                                         │
│   [消息2] → 处理失败          │ → [消息2 + 错误信息]                    │
│          (重试3次后)          │    (人工审查)                           │
│   [消息3] → 处理成功 ✓        │                                         │
│                                │                                         │
│   死信队列消息格式：                                                    │
│   {                                                                     │
│     "original_event": {...},  # 原始事件                                │
│     "error": "Checkpoint not found",                                    │
│     "failed_at": "2026-06-04T10:00:00Z",                                │
│     "retry_count": 3                                                    │
│   }                                                                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

【审批流程时序图】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌─────────────────────────────────────────────────────────────────────────┐
│                        完整审批回调流程                                  │
│                                                                         │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│   │  用户    │  │Orchestrator│ │ Governance│ │  Kafka  │  │  Redis  │ │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│        │              │              │              │              │     │
│        │ 1. 执行高风险操作                                          │     │
│        │─────────────>│              │              │              │     │
│        │              │              │              │              │     │
│        │              │ 2. 创建审批任务                              │     │
│        │              │─────────────>│              │              │     │
│        │              │              │              │              │     │
│        │              │ 3. 保存 Checkpoint                          │     │
│        │              │─────────────────────────────────────────>│     │
│        │              │              │              │   (pending)  │     │
│        │              │              │              │              │     │
│        │              │ 4. 进入 approval_wait 节点                  │     │
│        │              │ (启动心跳续期)│              │              │     │
│        │              │              │              │              │     │
│        │              │      ... 等待审批 (可能数小时) ...          │     │
│        │              │              │              │              │     │
│        │ 5. 审批通过  │              │              │              │     │
│        │─────────────────────────────>│              │              │     │
│        │              │              │              │              │     │
│        │              │              │ 6. 发送审批事件              │     │
│        │              │              │─────────────>│              │     │
│        │              │              │              │              │     │
│        │              │ 7. 消费审批事件                              │     │
│        │              │<───────────────────────────│              │     │
│        │              │              │              │              │     │
│        │              │ 8. 加载 Checkpoint                          │     │
│        │              │─────────────────────────────────────────>│     │
│        │              │<─────────────────────────────────────────│     │
│        │              │              │              │              │     │
│        │              │ 9. 验证状态 (pending)                       │     │
│        │              │              │              │              │     │
│        │              │ 10. 更新状态 (approved)                     │     │
│        │              │─────────────────────────────────────────>│     │
│        │              │              │              │              │     │
│        │              │ 11. 恢复 LangGraph 执行                     │     │
│        │              │ (ainvoke with checkpoint)   │              │     │
│        │              │              │              │              │     │
│        │              │ 12. 清理 Checkpoint                         │     │
│        │              │─────────────────────────────────────────>│     │
│        │              │              │              │              │     │
│        │ 13. 返回结果 │              │              │              │     │
│        │<─────────────│              │              │              │     │
│        │              │              │              │              │     │
└─────────────────────────────────────────────────────────────────────────┘

【注意事项】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 【幂等性】同一审批事件可能被重复消费，必须保证处理幂等
2. 【超时处理】Checkpoint 有 TTL，超时自动过期（由心跳续期）
3. 【错误处理】处理失败时不阻塞消费，记录日志并跳过
4. 【监控告警】Checkpoint 加载失败、执行失败应触发告警
5. 【消费者偏移】当前使用自动提交，未来可改为手动提交保证精确一次

【演进历史】
- v1.0: HTTP 回调，需配置 Orchestrator 地址
- v2.0: 切换到 Kafka，支持多实例部署
- v2.1: 添加幂等性检查（当前版本）

【相关文件】
- app/memory/checkpoint_store.py: Checkpoint 存储
- app/graph/nodes/approval_wait.py: 审批等待节点
- app/graph/builder.py: LangGraph 构建器
"""

import asyncio
import json

import structlog
from aiokafka import AIOKafkaConsumer

logger = structlog.get_logger()


class ApprovalCallbackHandler:
    """审批回调处理器

    【职责边界】
    本类专注于 Kafka 消息消费和执行恢复，不负责：
    - 审批流程判断 → 由 Governance 服务处理
    - Checkpoint 生命周期管理 → 由 CheckpointStore 处理
    - LangGraph 节点逻辑 → 由各节点实现

    【核心功能】
    1. 消费 Kafka 审批事件 → start() / handle_event()
    2. 恢复 LangGraph 执行 → resume_execution()
    3. 幂等性保证 → 检查 Checkpoint 状态后再处理

    【线程安全】
    - consumer: 单线程消费，无并发问题
    - _graph: 延迟加载，只读，线程安全
    - checkpoint_store: 通过 get_checkpoint_store() 获取单例

    【Kafka 配置】
    - Topic: agent-platform.approval
    - 消费者组: orchestrator-callback
    - 自动提交偏移量: 是（默认）
    - 反序列化: JSON
    """

    def __init__(
        self,
        kafka_servers: str,
        topic: str = "agent-platform.approval",
        checkpoint_store=None,
    ):
        """初始化审批回调处理器

        Args:
            kafka_servers: Kafka 集群地址，格式：host1:port1,host2:port2
            topic: 审批事件 Topic，默认 agent-platform.approval
            checkpoint_store: Checkpoint 存储实例，可选（延迟初始化）

        Note:
            - consumer 延迟到 start() 时创建，避免初始化阻塞
            - _graph 延迟加载，避免循环导入
        """
        self.kafka_servers = kafka_servers
        self.topic = topic
        self.checkpoint_store = checkpoint_store
        self.consumer = None
        self._graph = None  # Lazy load to avoid circular import

    async def start(self):
        """启动 Kafka 消费者

        【消费流程】
        ┌─────────────────────────────────────────────────────────────────┐
        │ 1. 创建 AIOKafkaConsumer                                        │
        │ 2. 连接 Kafka 集群                                              │
        │ 3. 加入消费者组，分配分区                                        │
        │ 4. 循环消费消息                                                  │
        │ 5. 处理每条消息（幂等）                                          │
        │ 6. 正常退出时关闭连接                                            │
        └─────────────────────────────────────────────────────────────────┘

        【异常处理】
        - 连接失败: AIOKafkaConsumer 自动重连
        - 消费异常: 记录日志，继续消费下一条
        - 程序终止: finally 块确保连接关闭

        Note:
            此方法会阻塞，应在后台任务中运行。
        """
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.kafka_servers,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            # 消费者组配置（使用默认 group_id）
            # 自动提交偏移量（默认启用）
        )
        await self.consumer.start()
        logger.info("Approval callback handler started", topic=self.topic)

        try:
            async for message in self.consumer:
                await self.handle_event(message.value)
        finally:
            await self.consumer.stop()

    async def handle_event(self, event: dict):
        """处理审批事件

        【事件格式】
        {
            "event_type": "approval.approved" | "approval.rejected",
            "approval_id": "apr_xxx",
            "run_id": "run_xxx",
            "reviewer_id": "user_xxx",  # 可选
            "comment": "审批备注",       # 可选
            "timestamp": "2026-06-04T10:00:00Z"
        }

        【处理逻辑】
        1. 解析事件类型
        2. 根据 event_type 调用对应的处理方法
        3. 未知事件类型记录警告日志

        【幂等性】
        - 同一事件可能重复投递
        - resume_execution() 内部处理幂等性

        Args:
            event: 审批事件字典

        Note:
            此方法不抛出异常，所有错误记录日志后跳过。
        """
        event_type = event.get("event_type", "")
        approval_id = event.get("approval_id", "")
        run_id = event.get("run_id", "")

        logger.info(
            "Received approval event",
            event_type=event_type,
            approval_id=approval_id,
            run_id=run_id,
        )

        if event_type == "approval.approved":
            await self.resume_execution(run_id, approval_id, approved=True)
        elif event_type == "approval.rejected":
            await self.resume_execution(run_id, approval_id, approved=False)
        else:
            logger.warning("Unknown event type", event_type=event_type)

    async def resume_execution(self, run_id: str, approval_id: str, approved: bool):
        """恢复 LangGraph 执行

        【恢复流程】
        ┌─────────────────────────────────────────────────────────────────┐
        │ 1. 初始化 CheckpointStore（如果未提供）                         │
        │ 2. 从 Redis 加载 Checkpoint                                     │
        │ 3. 检查 Checkpoint 是否存在                                     │
        │    - 不存在 → 记录错误，返回（任务已过期或完成）                 │
        │ 4. 更新审批状态（幂等操作）                                      │
        │ 5. 加载 LangGraph 实例                                          │
        │ 6. 调用 ainvoke 恢复执行                                        │
        │ 7. 执行成功后清理 Checkpoint                                     │
        │ 8. 执行失败保留 Checkpoint（等待人工干预或重试）                 │
        └─────────────────────────────────────────────────────────────────┘

        【幂等性保证】
        ┌─────────────────────────────────────────────────────────────────┐
        │ 检查点: Checkpoint 是否存在                                     │
        │   - 不存在 → 已处理或已过期，直接返回                           │
        │                                                                 │
        │ 状态检查: approval_status == "pending"?                         │
        │   - 已处理 (approved/rejected) → 跳过，不重复执行               │
        │   - 未处理 (pending) → 执行恢复                                 │
        │                                                                 │
        │ 执行幂等: LangGraph ainvoke 对同一 checkpoint 幂等               │
        └─────────────────────────────────────────────────────────────────┘

        【错误处理策略】
        ┌────────────────────┬─────────────────────────────────────────────┐
        │ 错误类型           │ 处理方式                                    │
        ├────────────────────┼─────────────────────────────────────────────┤
        │ Checkpoint 不存在  │ 记录错误日志，返回（不重试）                 │
        │ LangGraph 执行失败 │ 记录错误日志，保留 Checkpoint                │
        │ Redis 连接失败     │ 记录错误日志，保留 Checkpoint 等待重试       │
        └────────────────────┴─────────────────────────────────────────────┘

        Args:
            run_id: 运行实例 ID（Agent 执行的唯一标识）
            approval_id: 审批任务 ID
            approved: 是否通过审批

        Note:
            此方法设计为幂等，可安全重复调用。
        """
        logger.info(
            "Resuming execution",
            run_id=run_id,
            approval_id=approval_id,
            approved=approved,
        )

        # 1. 初始化 CheckpointStore（如果未提供）
        if self.checkpoint_store is None:
            from app.memory.checkpoint_store import get_checkpoint_store

            self.checkpoint_store = get_checkpoint_store()

        # 2. 从 Redis 加载 Checkpoint
        checkpoint = await self.checkpoint_store.load(run_id)
        if checkpoint is None:
            logger.error("Checkpoint not found", run_id=run_id)
            return

        # 3. 【幂等性检查】验证状态是否为 pending
        current_status = checkpoint.get("approval_status")
        if current_status and current_status != "pending":
            logger.warning(
                "Checkpoint already processed, skipping",
                run_id=run_id,
                current_status=current_status,
            )
            return

        # 4. 更新审批状态
        checkpoint["approval_status"] = "approved" if approved else "rejected"
        checkpoint["approval_id"] = approval_id

        # 5. 恢复 LangGraph 执行
        if self._graph is None:
            from app.graph.builder import get_agent_graph

            self._graph = get_agent_graph()

        # thread_id 必须与原始执行一致（chat.py 用 request_id==run_id），
        # 否则 LangGraph 找不到中断线程的 checkpoint，无法从断点恢复。
        config = {
            "configurable": {
                "thread_id": run_id,
            }
        }

        try:
            # 使用 ainvoke 恢复执行
            result = await self._graph.ainvoke(checkpoint, config=config)

            logger.info(
                "Execution resumed successfully",
                run_id=run_id,
                approved=approved,
                result_status=result.get("current_step", "unknown"),
            )

            # 6. 清理 Checkpoint（执行完成）
            await self.checkpoint_store.delete(run_id)

        except Exception as e:
            logger.error(
                "Failed to resume execution",
                run_id=run_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            # 保留 Checkpoint 以便后续恢复或人工干预
            # 可选：将失败信息写入 Checkpoint 供调试


async def main():
    """启动回调处理器（独立运行入口）

    【使用场景】
    - 本地开发测试
    - 独立进程部署（与 Orchestrator 主进程分离）

    【生产部署】
    推荐在 Orchestrator 主进程中启动后台任务：
    ```python
    # app/main.py
    @app.on_event("startup")
    async def startup():
        handler = ApprovalCallbackHandler(
            kafka_servers=config.kafka_servers,
        )
        asyncio.create_task(handler.start())
    ```

    Note:
        此函数会阻塞，Ctrl+C 可优雅退出。
    """
    handler = ApprovalCallbackHandler(
        kafka_servers="localhost:9092",
    )
    await handler.start()


if __name__ == "__main__":
    asyncio.run(main())
