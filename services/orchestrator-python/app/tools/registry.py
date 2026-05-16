"""工具注册表

【核心概念】工具注册中心
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

工具注册表是工具管理的核心组件，负责：
1. 工具注册与发现
2. 工具生命周期管理
3. 按类别/风险等级过滤
4. 工具调用路由

【设计模式】Registry Pattern
使用注册表模式的好处：
1. 解耦：工具定义与使用分离
2. 集中管理：统一的工具入口
3. 动态发现：运行时查找工具
4. 扩展性：新增工具无需修改调用方

【线程安全】
本注册表设计为单实例使用，不涉及跨线程共享。
如需跨线程使用，考虑使用 threading.Lock 保护。

【参考】
- Python Registry Pattern: https://martinfowler.com/eaaCatalog/registry.html
- FastAPI Depends: https://fastapi.tiangolo.com/tutorial/dependencies/
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING, Any, Callable

from app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolCategory,
    ToolMetadata,
    ToolProtocol,
    ToolResult,
)

if TYPE_CHECKING:
    pass

logger = structlog.get_logger()


class ToolNotFoundError(Exception):
    """工具未找到错误

    当请求的工具不存在时抛出。

    Attributes:
        tool_name: 请求的工具名称
    """

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool not found: {tool_name}")


class ToolRegistrationError(Exception):
    """工具注册错误

    当工具注册失败时抛出。

    Attributes:
        tool_name: 工具名称
        reason: 失败原因
    """

    def __init__(self, tool_name: str, reason: str):
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"Failed to register tool '{tool_name}': {reason}")


class ToolRegistry:
    """工具注册表

    管理所有已注册的工具，提供注册、查找、过滤功能。

    【核心方法】
    - register(tool): 注册工具
    - get(name): 获取工具
    - list_all(): 列出所有工具
    - filter_by_category(): 按类别过滤
    - filter_by_risk_level(): 按风险等级过滤

    【单例使用】
    推荐通过 FastAPI Depends 使用：
    ```python
    from fastapi import Depends
    from app.tools.registry import get_tool_registry, ToolRegistry

    async def my_endpoint(registry: ToolRegistry = Depends(get_tool_registry)):
        tool = registry.get("query_order")
    ```

    【注册时机】
    工具注册应在应用启动时完成：
    - FastAPI on_event("startup") 或 lifespan
    - 或在模块导入时（不推荐）

    Example:
        ```python
        # 创建注册表
        registry = ToolRegistry()

        # 注册工具
        registry.register(my_tool)

        # 获取工具
        tool = registry.get("query_order_status")

        # 按类别过滤
        query_tools = registry.filter_by_category(ToolCategory.QUERY)

        # 执行工具
        result = await tool.execute({"order_id": "ORD-123"})
        ```
    """

    def __init__(self):
        """初始化工具注册表"""
        self._tools: dict[str, ToolProtocol] = {}
        self._metadata_cache: dict[str, ToolMetadata] = {}

    def register(self, tool: ToolProtocol) -> None:
        """注册工具

        将工具添加到注册表，使其可被发现和调用。

        Args:
            tool: 要注册的工具实例

        Raises:
            ToolRegistrationError: 工具已存在或元数据无效

        Example:
            ```python
            registry.register(QueryOrderTool())
            registry.register(ExecutePaymentTool())
            ```
        """
        metadata = tool.metadata
        name = metadata.name

        # 检查是否已存在
        if name in self._tools:
            logger.warning(
                "tool_already_exists",
                tool_name=name,
                action="overwrite",
            )

        # 验证元数据
        if not name or not metadata.description:
            raise ToolRegistrationError(name, "Tool name and description are required")

        # 注册工具
        self._tools[name] = tool
        self._metadata_cache[name] = metadata

        logger.info(
            "tool_registered",
            tool_name=name,
            category=metadata.category.value,
            risk_level=metadata.risk_level.value,
        )

    def register_from_dict(
        self,
        tools: dict[str, Callable[[dict[str, Any]], ToolResult]],
        metadata_map: dict[str, ToolMetadata],
    ) -> None:
        """从字典批量注册工具

        用于注册简单函数式工具。

        Args:
            tools: 工具函数字典 {name: execute_func}
            metadata_map: 元数据字典 {name: metadata}

        Example:
            ```python
            def query_order(args: dict) -> ToolResult:
                return ToolResult(success=True, data={...})

            tools = {"query_order": query_order}
            metadata = {
                "query_order": ToolMetadata(
                    name="query_order",
                    description="查询订单",
                )
            }
            registry.register_from_dict(tools, metadata)
            ```
        """
        for name, execute_func in tools.items():
            metadata = metadata_map.get(name)
            if not metadata:
                raise ToolRegistrationError(name, "Metadata not found")

            # 创建简单工具包装器
            tool = _FunctionTool(execute_func, metadata)
            self.register(tool)

    def get(self, name: str) -> ToolProtocol:
        """获取工具

        根据名称获取已注册的工具。

        Args:
            name: 工具名称

        Returns:
            ToolProtocol: 工具实例

        Raises:
            ToolNotFoundError: 工具不存在

        Example:
            ```python
            tool = registry.get("query_order_status")
            result = await tool.execute({"order_id": "ORD-123"})
            ```
        """
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def get_metadata(self, name: str) -> ToolMetadata:
        """获取工具元数据

        Args:
            name: 工具名称

        Returns:
            ToolMetadata: 工具元数据

        Raises:
            ToolNotFoundError: 工具不存在
        """
        if name not in self._metadata_cache:
            raise ToolNotFoundError(name)
        return self._metadata_cache[name]

    def list_all(self) -> list[ToolMetadata]:
        """列出所有工具元数据

        Returns:
            list[ToolMetadata]: 所有已注册工具的元数据列表

        Example:
            ```python
            for meta in registry.list_all():
                print(f"{meta.name}: {meta.description}")
            ```
        """
        return list(self._metadata_cache.values())

    def list_names(self) -> list[str]:
        """列出所有工具名称

        Returns:
            list[str]: 所有已注册工具的名称列表
        """
        return list(self._tools.keys())

    def filter_by_category(self, category: ToolCategory) -> list[ToolMetadata]:
        """按类别过滤工具

        Args:
            category: 工具类别

        Returns:
            list[ToolMetadata]: 符合条件的工具元数据列表

        Example:
            ```python
            query_tools = registry.filter_by_category(ToolCategory.QUERY)
            ```
        """
        return [
            meta
            for meta in self._metadata_cache.values()
            if meta.category == category
        ]

    def filter_by_risk_level(
        self,
        risk_level: RiskLevel,
        include_lower: bool = True,
    ) -> list[ToolMetadata]:
        """按风险等级过滤工具

        Args:
            risk_level: 风险等级
            include_lower: 是否包含更低风险等级的工具

        Returns:
            list[ToolMetadata]: 符合条件的工具元数据列表

        Example:
            ```python
            # 只获取高风险工具
            high_risk_tools = registry.filter_by_risk_level(RiskLevel.HIGH, include_lower=False)

            # 获取中等及以下风险工具
            safe_tools = registry.filter_by_risk_level(RiskLevel.MEDIUM, include_lower=True)
            ```
        """
        risk_order = {
            RiskLevel.LOW: 0,
            RiskLevel.MEDIUM: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }

        if include_lower:
            return [
                meta
                for meta in self._metadata_cache.values()
                if risk_order[meta.risk_level] <= risk_order[risk_level]
            ]
        else:
            return [
                meta
                for meta in self._metadata_cache.values()
                if meta.risk_level == risk_level
            ]

    def filter(
        self,
        category: ToolCategory | None = None,
        risk_level: RiskLevel | None = None,
        requires_approval: bool | None = None,
        tags: list[str] | None = None,
    ) -> list[ToolMetadata]:
        """多条件过滤工具

        Args:
            category: 按类别过滤（可选）
            risk_level: 按风险等级过滤（可选）
            requires_approval: 按是否需要审批过滤（可选）
            tags: 按标签过滤（可选，匹配任意标签）

        Returns:
            list[ToolMetadata]: 符合所有条件的工具元数据列表

        Example:
            ```python
            # 获取所有需要审批的 ACTION 类工具
            tools = registry.filter(
                category=ToolCategory.ACTION,
                requires_approval=True
            )

            # 获取带 "payment" 标签的工具
            payment_tools = registry.filter(tags=["payment"])
            ```
        """
        result = list(self._metadata_cache.values())

        if category is not None:
            result = [m for m in result if m.category == category]

        if risk_level is not None:
            result = [m for m in result if m.risk_level == risk_level]

        if requires_approval is not None:
            result = [m for m in result if m.requires_approval == requires_approval]

        if tags:
            result = [m for m in result if any(tag in m.tags for tag in tags)]

        return result

    def exists(self, name: str) -> bool:
        """检查工具是否存在

        Args:
            name: 工具名称

        Returns:
            bool: 工具是否存在
        """
        return name in self._tools

    def unregister(self, name: str) -> bool:
        """注销工具

        从注册表中移除工具。通常用于动态工具管理。

        Args:
            name: 工具名称

        Returns:
            bool: 是否成功注销（False 表示工具不存在）

        Example:
            ```python
            if registry.unregister("temp_tool"):
                print("Tool removed")
            ```
        """
        if name in self._tools:
            del self._tools[name]
            del self._metadata_cache[name]
            logger.info("tool_unregistered", tool_name=name)
            return True
        return False

    def clear(self) -> None:
        """清空所有工具

        通常用于测试或重新初始化。
        """
        self._tools.clear()
        self._metadata_cache.clear()
        logger.info("tool_registry_cleared")

    def __len__(self) -> int:
        """返回已注册工具数量"""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """检查工具是否存在（支持 `in` 操作符）"""
        return name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry(tools={len(self._tools)})"


class _FunctionTool(ToolProtocol):
    """函数式工具包装器

    将简单函数包装为工具协议实现。

    用于 register_from_dict 方法。
    """

    def __init__(
        self,
        execute_func: Callable[[dict[str, Any]], ToolResult],
        metadata: ToolMetadata,
    ):
        self._execute_func = execute_func
        self._metadata = metadata

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """执行工具函数"""
        # 支持同步和异步函数
        import asyncio

        result = self._execute_func(arguments)
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def validate_arguments(self, arguments: dict[str, Any]) -> bool:
        """校验参数"""
        import jsonschema

        schema = self._metadata.schema
        if not schema:
            return True

        try:
            jsonschema.validate(arguments, schema)
            return True
        except jsonschema.ValidationError:
            return False


# 全局注册表实例
_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表单例

    FastAPI Depends 使用示例：
    ```python
    from fastapi import Depends
    from app.tools.registry import get_tool_registry, ToolRegistry

    async def my_endpoint(
        registry: ToolRegistry = Depends(get_tool_registry)
    ):
        tools = registry.list_all()
    ```

    Returns:
        ToolRegistry: 工具注册表实例
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_tool_registry() -> None:
    """重置工具注册表

    通常用于测试环境。
    """
    global _global_registry
    if _global_registry is not None:
        _global_registry.clear()
    _global_registry = None