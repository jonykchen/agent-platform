"""Agent 运行取消检查

提供统一的取消标志检查逻辑，供各 graph 节点在执行入口调用。

【设计说明】
取消机制基于 Redis 标志：
- cancel_run API 设置 `run:{run_id}:cancel` 键
- 各节点入口调用 check_cancel_flag() 检查该键
- 若发现取消标志，返回取消状态字典，Agent 图将终止执行

【为什么不直接在 state 中传递】
LangGraph 的 state 在节点间是只读追加的，无法在运行期间从外部注入取消信号。
Redis 作为共享状态存储，可被 API 层写入、节点层读取，实现跨进程取消协调。

【run_id 的来源】
run_id 存储在 state.metadata["run_id"] 中，由 create_initial_state() 写入。
对于未传入 run_id 的场景（如同步模式），使用 request_id 作为降级方案。
"""

from __future__ import annotations

import structlog

from app.infrastructure.redis_client import get_redis

logger = structlog.get_logger()

# 取消时返回的状态字典模板
CANCEL_STATE = {
    "current_step": "cancelled",
    "error": "用户取消了任务",
}


async def check_cancel_flag(state: dict) -> dict | None:
    """检查 Agent 运行是否已被取消

    从 state.metadata 中提取 run_id（或降级使用 request_id），
    检查 Redis 中的取消标志。

    Args:
        state: 当前 AgentState（需包含 request_id，可选 metadata.run_id）

    Returns:
        若已取消返回取消状态字典，否则返回 None
    """
    # 优先使用 metadata.run_id，降级使用 request_id
    metadata = state.get("metadata", {})
    run_id = metadata.get("run_id") if isinstance(metadata, dict) else None
    request_id = state.get("request_id", "")
    cancel_key = f"run:{run_id}:cancel" if run_id else None

    if not cancel_key:
        return None

    try:
        redis_client = get_redis()
        cancelled = await redis_client.exists(cancel_key)
        if cancelled:
            logger.info(
                "run_cancelled_at_checkpoint",
                run_id=run_id,
                request_id=request_id,
            )
            return {
                **CANCEL_STATE,
                "request_id": request_id,
            }
    except Exception as e:
        # Redis 不可用时不应阻塞正常流程，仅记录警告
        logger.warning(
            "cancel_check_failed",
            run_id=run_id,
            request_id=request_id,
            error=str(e),
        )

    return None
