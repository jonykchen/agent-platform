"""LangGraph Checkpoint 存储

使用 Redis 持久化 Agent 状态，支持暂停/恢复。
"""

import json
from datetime import datetime

import redis.asyncio as redis
import structlog

from app.core.config import config

logger = structlog.get_logger()


class CheckpointStore:
    """Redis Checkpoint 存储

    用于持久化 LangGraph 状态，支持：
    - 暂停/恢复执行
    - 超时恢复
    - 审批回调恢复
    """

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or config.redis_url
        self._client: redis.Redis | None = None

    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._client

    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _key(self, run_id: str) -> str:
        """生成 Redis 键"""
        return f"checkpoint:{run_id}"

    async def save(self, run_id: str, checkpoint: dict, ttl_seconds: int = 7200) -> None:
        """保存 Checkpoint

        Args:
            run_id: 运行实例 ID
            checkpoint: 状态快照
            ttl_seconds: 过期时间（默认 2 小时）
        """
        client = await self._get_client()
        key = self._key(run_id)

        checkpoint_data = {
            "run_id": run_id,
            "checkpoint": checkpoint,
            "created_at": datetime.utcnow().isoformat(),
        }

        await client.set(key, json.dumps(checkpoint_data), ex=ttl_seconds)

        logger.info(
            "Checkpoint saved",
            run_id=run_id,
            ttl=ttl_seconds,
        )

    async def load(self, run_id: str) -> dict | None:
        """加载 Checkpoint

        Args:
            run_id: 运行实例 ID

        Returns:
            Checkpoint 数据，不存在返回 None
        """
        client = await self._get_client()
        key = self._key(run_id)

        data = await client.get(key)
        if not data:
            return None

        checkpoint_data = json.loads(data)

        logger.info(
            "Checkpoint loaded",
            run_id=run_id,
            created_at=checkpoint_data.get("created_at"),
        )

        return checkpoint_data.get("checkpoint")

    async def delete(self, run_id: str) -> None:
        """删除 Checkpoint"""
        client = await self._get_client()
        key = self._key(run_id)
        await client.delete(key)
        logger.info("Checkpoint deleted", run_id=run_id)

    async def exists(self, run_id: str) -> bool:
        """检查 Checkpoint 是否存在"""
        client = await self._get_client()
        key = self._key(run_id)
        return await client.exists(key) > 0

    async def list_pending(self, session_id: str | None = None) -> list[dict]:
        """列出待恢复的 Checkpoint

        Args:
            session_id: 可选，过滤特定会话

        Returns:
            Checkpoint 列表
        """
        client = await self._get_client()

        # 扫描所有 checkpoint 键
        pattern = "checkpoint:*"
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)

        checkpoints = []
        for key in keys:
            data = await client.get(key)
            if data:
                checkpoint_data = json.loads(data)
                checkpoint = checkpoint_data.get("checkpoint", {})

                # 过滤会话
                if session_id and checkpoint.get("session_id") != session_id:
                    continue

                # 检查是否在等待审批
                approval_status = checkpoint.get("approval_status")
                if approval_status == "pending":
                    checkpoints.append({
                        "run_id": checkpoint_data.get("run_id"),
                        "session_id": checkpoint.get("session_id"),
                        "approval_id": checkpoint.get("approval_id"),
                        "created_at": checkpoint_data.get("created_at"),
                    })

        return checkpoints

    async def update_approval_status(
        self,
        run_id: str,
        status: str,
        reviewer_id: str | None = None,
        comment: str | None = None,
    ) -> None:
        """更新审批状态

        Args:
            run_id: 运行实例 ID
            status: 新状态 (approved/rejected)
            reviewer_id: 审批人 ID
            comment: 审批备注
        """
        checkpoint = await self.load(run_id)
        if not checkpoint:
            logger.warning("Checkpoint not found for approval update", run_id=run_id)
            return

        checkpoint["approval_status"] = status
        checkpoint["approval_reviewer"] = reviewer_id
        checkpoint["approval_comment"] = comment
        checkpoint["approval_updated_at"] = datetime.utcnow().isoformat()

        await self.save(run_id, checkpoint)

        logger.info(
            "Approval status updated",
            run_id=run_id,
            status=status,
        )


# 全局实例
_store = None


def get_checkpoint_store() -> CheckpointStore:
    """获取 Checkpoint 存储实例"""
    global _store
    if _store is None:
        _store = CheckpointStore()
    return _store