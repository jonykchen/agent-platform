"""Kafka 回调恢复机制 - Orchestrator 消费审批结果"""

import asyncio
import json

import structlog
from aiokafka import AIOKafkaConsumer

logger = structlog.get_logger()


class ApprovalCallbackHandler:
    """审批回调处理器

    消费 Kafka 中的审批结果事件，恢复 LangGraph Checkpoint 执行。
    """

    def __init__(
        self,
        kafka_servers: str,
        topic: str = "agent-platform.approval",
        checkpoint_store=None,
    ):
        self.kafka_servers = kafka_servers
        self.topic = topic
        self.checkpoint_store = checkpoint_store
        self.consumer = None
        self._graph = None  # Lazy load to avoid circular import

    async def start(self):
        """启动消费者"""
        self.consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.kafka_servers,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        )
        await self.consumer.start()
        logger.info("Approval callback handler started", topic=self.topic)

        try:
            async for message in self.consumer:
                await self.handle_event(message.value)
        finally:
            await self.consumer.stop()

    async def handle_event(self, event: dict):
        """处理审批事件"""
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

        Args:
            run_id: 运行实例 ID
            approval_id: 审批任务 ID
            approved: 是否通过审批
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

        # 3. 更新审批状态
        checkpoint["approval_status"] = "approved" if approved else "rejected"
        checkpoint["approval_id"] = approval_id

        # 4. 恢复 LangGraph 执行
        if self._graph is None:
            from app.graph.builder import get_agent_graph
            self._graph = get_agent_graph()

        config = {
            "configurable": {
                "thread_id": checkpoint.get("session_id", run_id),
            }
        }

        try:
            # 使用 ainvoke 恢复执行
            result = await self._graph.ainvoke(
                checkpoint,
                config=config,
            )

            logger.info(
                "Execution resumed successfully",
                run_id=run_id,
                approved=approved,
                result_status=result.get("current_step", "unknown"),
            )

            # 5. 清理 Checkpoint（执行完成）
            await self.checkpoint_store.delete(run_id)

        except Exception as e:
            logger.error(
                "Failed to resume execution",
                run_id=run_id,
                error=str(e),
            )
            # 保留 Checkpoint 以便后续恢复


async def main():
    """启动回调处理器"""
    handler = ApprovalCallbackHandler(
        kafka_servers="localhost:9092",
    )
    await handler.start()


if __name__ == "__main__":
    asyncio.run(main())
