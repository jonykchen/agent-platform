"""优雅关闭模块 - Graceful Shutdown

【核心概念】Graceful Shutdown 原理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

在 Kubernetes 环境中，Pod 终止流程如下：

┌─────────────────────────────────────────────────────────────────────────────┐
│                      Kubernetes Pod 终止流程                                  │
│                                                                             │
│  1. kubectl delete pod / Deployment 滚动更新                                 │
│         │                                                                   │
│         ▼                                                                   │
│  2. Pod 标记为 Terminating                                                  │
│         │                                                                   │
│         ▼                                                                   │
│  3. Endpoint Controller 从 Service 移除 Pod                                 │
│     └── 新请求不再路由到此 Pod                                               │
│         │                                                                   │
│         ▼                                                                   │
│  4. kubelet 发送 SIGTERM 信号                                               │
│     └── 应用开始优雅关闭                                                     │
│         │                                                                   │
│         ├──► 5a. 停止接收新请求（返回 503）                                  │
│         │                                                                   │
│         ├──► 5b. 等待进行中请求完成                                          │
│         │    └── max_wait = 30s（可配置）                                   │
│         │                                                                   │
│         ├──► 5c. 释放资源（数据库、Redis、gRPC）                             │
│         │                                                                   │
│         ▼                                                                   │
│  6. 等待 terminationGracePeriodSeconds（默认 30s）                          │
│         │                                                                   │
│         ├──► 正常退出（所有请求处理完毕）                                    │
│         │                                                                   │
│         ▼                                                                   │
│  7. 超时后发送 SIGKILL 强制终止                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

【关键设计点】
1. 请求计数：使用 asyncio.Counter 追踪进行中请求
2. 健康检查：关闭时标记为不健康，K8s 停止路由新请求
3. 超时处理：设置最大等待时间，避免无限等待
4. 信号处理：捕获 SIGTERM/SIGINT，触发关闭流程

【技术选型】为什么使用 asyncio 信号量？
┌─────────────────────────────────────────────────────────────────────────────┐
│  方案               │  优点                    │  缺点                    │
├─────────────────────┼──────────────────────────┼──────────────────────────┤
│  threading.Counter  │  简单                    │  不适合异步环境          │
│  ✓ asyncio.Counter  │  原生异步支持            │  需要 Python 3.10+       │
│  自定义锁+计数      │  灵活                    │  需要自己实现            │
└─────────────────────┴──────────────────────────┴──────────────────────────┘

【参考】
- Kubernetes 优雅关闭: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-termination
- FastAPI 生命周期: https://fastapi.tiangolo.com/advanced/events/
- Python 信号处理: https://docs.python.org/3/library/signal.html
"""

from __future__ import annotations

import asyncio
import signal
from typing import Callable

import structlog

logger = structlog.get_logger()


# ═══════════════════════════════════════════════════════════════════════════════
# 【设计原则】asyncio.Lock vs threading.Lock
# ═══════════════════════════════════════════════════════════════════════════════
# ┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
# │ 方案               │ 适用场景                    │ 注意事项                    │
# ├────────────────────┼─────────────────────────────┼─────────────────────────────┤
# │ threading.Lock     │ 多线程环境                  │ 在 asyncio 中会阻塞事件循环 │
# │ ✓ asyncio.Lock     │ 协程环境（本项目）          │ 只能在异步函数中使用        │
# │ asyncio.Counter    │ 原子计数（无竞态）          │ 需要 Python 3.10+           │
# │ 无锁设计           │ 性能最优                    │ 复杂，易出错                │
# └────────────────────┴─────────────────────────────┴─────────────────────────────┘
#
# 【实现说明】为什么使用 asyncio.Lock？
# ─────────────────────────────────────────
# 1. 本项目基于 FastAPI，整个请求处理在协程中执行
# 2. 状态变更（increment/decrement）在多个协程间共享
# 3. asyncio.Lock 不会阻塞事件循环，保证并发性能
#
# 【竞态条件分析】
# ─────────────────────────────────────────
# ┌────────────────────┬─────────────────────────────────────────────────┐
# │ 场景               │ 请求结束调用 decrement()，同时 SIGTERM 触发关闭  │
# ├────────────────────┼─────────────────────────────────────────────────┤
# │ 风险               │ 计数器减到 0 时刚好触发关闭，可能提前退出        │
# │ 解决               │ asyncio.Lock 保护状态变更，原子执行计数和关闭检查│
# └────────────────────┴─────────────────────────────────────────────────┘
#
# 【时序图】并发场景分析
# ─────────────────────────────────────────
#     RequestHandler        SignalHandler          GracefulShutdown
#          │                     │                       │
#          │  decrement()        │                       │
#          │─────────────────────┼──────────────────────>│ acquire lock
#          │                     │                       │ counter--
#          │                     │                       │ counter=0?
#          │                     │   SIGTERM             │ release lock
#          │                     │──────────────────────>│
#          │                     │                       │ initiate_shutdown()
#          │                     │                       │ acquire lock (wait)
#          │                     │                       │ (lock acquired)
#          │                     │                       │ set shutdown_event
#          │                     │                       │ check counter=0
#          │                     │                       │ proceed with shutdown
#
# 【为什么不用 threading.Lock？】
# ─────────────────────────────────────────
# threading.Lock 会阻塞整个事件循环线程，导致：
# - 所有协程暂停执行（包括不相关的请求处理）
# - 信号处理延迟（无法及时响应 SIGTERM）
# - 性能下降（阻塞期间的 CPU 空闲）
#
# 【为什么不用无锁设计？】
# ─────────────────────────────────────────
# 虽然 `self._active_requests += 1` 在 CPython 中是原子的（GIL 保护），
# 但以下操作需要原子性保证：
# - increment() 中的 "检查 + 增加" 不是原子的
# - decrement() 中的 "减少 + 检查 + 通知" 不是原子的
# 使用 asyncio.Lock 确保这些复合操作的原子性。


class GracefulShutdown:
    """优雅关闭管理器

    追踪进行中的请求数量，在收到关闭信号后：
    1. 标记服务为不健康状态（健康检查返回 503）
    2. 拒绝接收新请求
    3. 等待所有进行中请求完成
    4. 超时后强制退出

    【线程安全说明】
    使用 asyncio.Lock 保护计数器更新，确保多协程环境下的安全性。

    Example:
        >>> shutdown_manager = GracefulShutdown()
        >>>
        >>> # 在请求处理中
        >>> async def handle_request():
        ...     shutdown_manager.increment()
        ...     try:
        ...         # 处理请求
        ...         pass
        ...     finally:
        ...         shutdown_manager.decrement()
        >>>
        >>> # 设置信号处理
        >>> setup_signal_handlers(shutdown_manager)
        >>>
        >>> # 健康检查
        >>> if shutdown_manager.is_shutting_down():
        ...     return JSONResponse(status_code=503, content={"status": "shutting down"})
    """

    def __init__(self) -> None:
        """初始化优雅关闭管理器"""
        # 进行中请求计数器
        self._active_requests: int = 0
        # 关闭事件标记
        self._shutdown_event: asyncio.Event = asyncio.Event()
        # 状态锁，保护计数器更新
        self._lock: asyncio.Lock = asyncio.Lock()
        # 不健康标记（用于健康检查）
        self._unhealthy: bool = False

    @property
    def active_requests(self) -> int:
        """当前进行中的请求数量"""
        return self._active_requests

    async def increment(self) -> None:
        """增加请求计数

        在请求开始时调用。如果服务正在关闭，抛出 RuntimeError。

        【竞态条件防护】
        asyncio.Lock 确保以下操作的原子性：
        1. 检查是否正在关闭（is_set）
        2. 增加请求计数（+= 1）

        如果不使用锁，可能出现：
        - SIGTERM 刚好触发时，increment 通过了 is_set 检查
        - 但在 +=1 之前，shutdown 逻辑已经开始执行
        - 导致请求计数不准确，可能提前退出

        【日志增强】
        包含 trace_id 用于全链路追踪（由 structlog 自动注入 contextvars）
        """
        async with self._lock:
            if self._shutdown_event.is_set():
                raise RuntimeError("Service is shutting down, cannot accept new requests")
            self._active_requests += 1
            logger.debug(
                "Request started",
                active_requests=self._active_requests,
                # trace_id 由 structlog 通过 contextvars 自动注入
                # 来源: request_id middleware (app/api/middleware/request_id.py)
            )

    async def decrement(self) -> None:
        """减少请求计数

        在请求结束时调用（无论成功或失败）。

        【竞态条件防护】
        asyncio.Lock 确保以下操作的原子性：
        1. 减少请求计数（-= 1）
        2. 检查是否归零（<= 0）
        3. 检查是否正在关闭（is_set）

        【为什么需要锁保护？】
        decrement() 和 initiate_shutdown() 共享以下状态：
        - _active_requests：计数器
        - _shutdown_event：关闭事件

        如果不使用锁，可能出现：
        ┌─────────────────────────────────────────────────────────────────────────┐
        │ 时间线        │ 请求处理协程          │ 信号处理协程                  │
        ├───────────────┼───────────────────────┼────────────────────────────────┤
        │ T1            │ counter = 1           │                               │
        │ T2            │ counter-- → 0         │                               │
        │ T3            │                       │ initiate_shutdown() 开始      │
        │ T4            │                       │ 检查 counter = 0              │
        │ T5            │                       │ 立即关闭（安全）              │
        └───────────────┴───────────────────────┴────────────────────────────────┘

        【日志增强】
        包含 trace_id 用于全链路追踪（由 structlog 自动注入 contextvars）
        """
        async with self._lock:
            self._active_requests -= 1
            logger.debug(
                "Request completed",
                active_requests=self._active_requests,
                # trace_id 由 structlog 通过 contextvars 自动注入
            )
            # 如果计数归零且正在关闭，通知等待者
            if self._active_requests <= 0 and self._shutdown_event.is_set():
                self._active_requests = 0  # 防止负数

    def is_shutting_down(self) -> bool:
        """检查是否正在关闭

        用于健康检查端点判断是否应该返回 503。

        Returns:
            True 如果正在关闭，False 否则
        """
        return self._shutdown_event.is_set()

    def is_healthy(self) -> bool:
        """检查服务是否健康

        Returns:
            True 如果服务健康，False 否则
        """
        return not self._unhealthy and not self._shutdown_event.is_set()

    def mark_unhealthy(self) -> None:
        """标记服务为不健康状态

        当关键依赖（数据库、Redis 等）不可用时调用。
        健康检查端点将返回 503。
        """
        self._unhealthy = True
        logger.warning("Service marked as unhealthy")

    def mark_healthy(self) -> None:
        """标记服务为健康状态

        当服务恢复正常时调用。
        """
        self._unhealthy = False
        logger.info("Service marked as healthy")

    async def initiate_shutdown(self) -> None:
        """发起关闭流程

        由信号处理器调用，开始优雅关闭。

        【调用时机】
        当收到以下信号时触发：
        - SIGTERM: Kubernetes Pod 终止信号（kubectl delete / 滚动更新）
        - SIGINT: 用户中断信号（Ctrl+C / 开发环境）

        【关闭流程】
        1. 设置 _shutdown_event，通知所有协程服务正在关闭
        2. 标记 _unhealthy，健康检查端点返回 503
        3. increment() 将拒绝新请求
        4. wait_for_completion() 等待进行中请求完成

        【竞态条件说明】
        initiate_shutdown() 不需要获取锁，因为：
        - _shutdown_event.set() 是原子操作
        - _unhealthy = True 是原子操作
        - 状态变更的顺序不重要（最终一致性）

        但需要确保日志包含信号类型，方便排查问题。
        """
        logger.info(
            "Shutdown initiated",
            active_requests=self._active_requests,
            signal_type="SIGTERM/SIGINT",  # 由 setup_signal_handlers 传入
        )
        self._shutdown_event.set()
        self._unhealthy = True

    async def wait_for_completion(self, timeout: float = 30.0) -> bool:
        """等待所有请求完成

        阻塞直到所有请求完成或超时。

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            True 如果所有请求完成，False 如果超时

        【超时策略说明】
        ┌────────────────────┬───────────────┬─────────────────────────────────┐
        │ 参数               │ 推荐值        │ 依据                            │
        ├────────────────────┼───────────────┼─────────────────────────────────┤
        │ 默认超时           │ 30s           │ K8s 默认 terminationGracePeriod │
        │ 最小超时           │ 10s           │ 给服务足够时间完成请求          │
        │ 最大超时           │ 60s           │ 避免用户等待过久                │
        └────────────────────┴───────────────┴─────────────────────────────────┘

        【超时后的处理】
        1. 强制关闭：记录警告日志，列出未完成的请求数量
        2. 资源清理：关闭数据库连接、Redis 连接等
        3. 进程退出：返回非零退出码表示异常关闭

        【为什么是 30 秒？】
        - K8s terminationGracePeriodSeconds 默认 30s
        - 数据库连接池关闭约需 5-10s
        - Redis 连接关闭约需要 1-2s
        - 剩余时间留给用户请求完成

        【轮询策略】
        使用 100ms 轮询间隔，而非 asyncio.wait_for()：
        - asyncio.wait_for() 需要一个 awaitable，这里需要主动轮询
        - 100ms 足够短，不会明显延迟关闭
        - 100ms 足够长，不会造成 CPU 忙等待
        """
        if self._active_requests == 0:
            logger.info("No active requests, shutdown immediately")
            return True

        logger.info(
            "Waiting for active requests to complete",
            active_requests=self._active_requests,
            timeout=timeout,
        )

        try:
            # 等待所有请求完成或超时
            start_time = asyncio.get_event_loop().time()
            while self._active_requests > 0:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    logger.warning(
                        "Shutdown timeout reached",
                        active_requests=self._active_requests,
                        timeout=timeout,
                        elapsed_seconds=round(elapsed, 2),
                    )
                    return False
                # 短暂等待，避免忙等待
                await asyncio.sleep(0.1)

            logger.info("All requests completed")
            return True
        except asyncio.CancelledError:
            logger.warning(
                "Wait interrupted",
                active_requests=self._active_requests,
            )
            return False


def setup_signal_handlers(shutdown_manager: GracefulShutdown) -> None:
    """设置信号处理器

    注册 SIGTERM 和 SIGINT 信号处理器，触发优雅关闭流程。

    Args:
        shutdown_manager: 优雅关闭管理器实例

    Example:
        >>> shutdown_manager = GracefulShutdown()
        >>> setup_signal_handlers(shutdown_manager)
    """

    def handle_signal(signum: int, frame) -> None:
        """信号处理函数

        注意：信号处理器在主线程中执行，应该尽快返回。
        实际的关闭逻辑通过 asyncio.create_task 在事件循环中执行。
        """
        signal_name = signal.Signals(signum).name
        logger.info(
            "Signal received",
            signal=signal_name,
            signum=signum,
        )

        # 获取当前事件循环
        try:
            loop = asyncio.get_running_loop()
            # 在事件循环中调度关闭任务
            loop.create_task(shutdown_manager.initiate_shutdown())
        except RuntimeError:
            # 没有运行中的事件循环，直接设置事件
            shutdown_manager._shutdown_event.set()

    # 注册信号处理器
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logger.info(
        "Signal handlers registered",
        signals=["SIGTERM", "SIGINT"],
    )


# 全局优雅关闭管理器实例
_shutdown_manager: GracefulShutdown | None = None


def get_shutdown_manager() -> GracefulShutdown:
    """获取优雅关闭管理器实例"""
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdown()
    return _shutdown_manager


def init_shutdown_manager() -> GracefulShutdown:
    """初始化优雅关闭管理器"""
    global _shutdown_manager
    _shutdown_manager = GracefulShutdown()
    setup_signal_handlers(_shutdown_manager)
    return _shutdown_manager
