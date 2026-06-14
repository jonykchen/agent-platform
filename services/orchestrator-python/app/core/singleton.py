"""异步单例装饰器

解决 Python async 应用中 `global _store; if _store is None: _store = X` 模式
在并发协程下可能重复创建实例的问题。

【问题分析】
┌──────────────────────────────────────────────────────────────┐
│ 协程 A                      │ 协程 B                        │
├──────────────────────────────┼──────────────────────────────┤
│ if _store is None:  ← True  │                              │
│                              │ if _store is None:  ← True   │
│ _store = ExpensiveObj()      │                              │
│                              │ _store = ExpensiveObj()  ← 重复创建 │
└──────────────────────────────┴──────────────────────────────┘

【解决方案】
使用 asyncio.Lock 保护初始化，确保只有一个协程执行创建逻辑，
其他协程等待后直接获取已创建的实例。

【使用方式】
    @async_singleton
    async def get_my_service() -> MyService:
        return MyService(expensive_config)

    # 调用
    service = await get_my_service()

【注意】
- 装饰器要求函数是 async 的
- 适用于「首次创建后不变」的单例场景
- 不适用于需要热重载的配置
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

# 全局锁注册表：每个装饰的函数对应一把锁
_locks: dict[str, asyncio.Lock] = {}
# 全局实例注册表：每个装饰的函数对应一个实例
_instances: dict[str, Any] = {}


def async_singleton(func: Callable[..., T]) -> Callable[..., T]:
    """异步单例装饰器

    确保被装饰的 async 工厂函数只执行一次实例创建，
    后续调用直接返回已创建的实例。

    Args:
        func: 异步工厂函数，返回单例实例

    Returns:
        包装后的异步函数，具有单例语义
    """
    key = f"{func.__module__}.{func.__qualname__}"

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        # 快速路径：实例已存在直接返回（无需加锁）
        if key in _instances:
            return _instances[key]

        # 获取或创建该函数对应的锁
        if key not in _locks:
            _locks[key] = asyncio.Lock()

        async with _locks[key]:
            # 双重检查：等待锁后再次确认实例是否已创建
            if key in _instances:
                return _instances[key]

            instance = await func(*args, **kwargs)
            _instances[key] = instance
            return instance

    # 暴露 reset 方法用于测试
    def _reset() -> None:
        _instances.pop(key, None)
        _locks.pop(key, None)

    wrapper._reset = _reset  # type: ignore[attr-defined]
    return wrapper
