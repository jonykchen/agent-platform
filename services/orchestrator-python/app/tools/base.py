"""工具基类和协议定义

【核心概念】工具抽象层
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

工具是 Agent 与外部系统交互的核心桥梁。通过定义统一的工具接口，
我们实现了：
1. 工具实现的解耦 - 不同工具可以独立开发和测试
2. 工具注册的统一 - 通过注册表管理所有工具
3. 工具调用的标准化 - 统一的输入输出格式

【技术选型】Protocol vs ABC
┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Protocol (选择)    │ • 结构化子类型（鸭子类型）  │ • 无运行时检查              │
│                    │ • 零继承开销                │ • IDE 支持较弱               │
│                    │ • 灵活，可用于已有类        │                              │
│                    │ • Python 3.8+ 原生支持     │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ ABC (选择)         │ • 强制子类实现              │ • 继承链复杂                │
│                    │ • 运行时类型检查            │ • 与已有类集成困难           │
│                    │ • IDE 支持好                │                              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【设计原则】
- ToolProtocol: 定义工具接口，用于类型检查
- BaseTool: 提供通用实现，减少重复代码
- ToolResult: 标准化输出格式，支持成功/失败状态
- ToolMetadata: 工具元信息，用于注册和过滤

【参考】
- Python Protocol PEP 544: https://peps.python.org/pep-0544/
- LangChain Tool 设计: https://python.langchain.com/docs/modules/tools/
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """风险等级枚举

    用于工具的风险评估和权限控制。
    风险等级越高，需要的审批流程越严格。
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolCategory(str, Enum):
    """工具类别枚举

    用于工具分类和过滤。
    不同类别的工具有不同的权限模型和调用限制。
    """

    QUERY = "query"  # 查询类工具，只读操作
    ACTION = "action"  # 动作类工具，有副作用
    SYSTEM = "system"  # 系统类工具，运维使用
    INTEGRATION = "integration"  # 外部集成工具


class ToolResult(BaseModel):
    """工具执行结果

    标准化的工具输出格式，包含执行状态、结果数据和错误信息。

    Attributes:
        success: 执行是否成功
        data: 执行结果数据（成功时）
        error: 错误信息（失败时）
        error_code: 错误码，遵循 G-ERR-* 规范
        metadata: 额外元数据，如耗时、缓存状态等

    Example:
        成功结果：
        ```python
        result = ToolResult(
            success=True,
            data={"order_id": "ORD-123", "status": "completed"},
            metadata={"latency_ms": 150, "cache_hit": False}
        )
        ```

        失败结果：
        ```python
        result = ToolResult(
            success=False,
            error="订单不存在",
            error_code="ERR_TOOL_ORDER_NOT_FOUND"
        )
        ```
    """

    success: bool = Field(..., description="执行是否成功")
    data: dict[str, Any] | None = Field(default=None, description="执行结果数据")
    error: str | None = Field(default=None, description="错误信息")
    error_code: str | None = Field(default=None, description="错误码")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    model_config = {"frozen": False}  # 允许修改，方便测试


class ToolMetadata(BaseModel):
    """工具元数据

    包含工具的描述性信息，用于注册、发现和权限控制。

    Attributes:
        name: 工具唯一标识，格式为 verb_noun，如 query_order_status
        description: 工具描述，用于 LLM 理解工具用途
        category: 工具类别
        risk_level: 风险等级
        version: 工具版本，语义化版本号
        requires_auth: 是否需要认证
        requires_approval: 是否需要审批（高风险操作）
        schema: JSON Schema 格式的参数定义
        tags: 标签列表，用于过滤和搜索
    """

    name: str = Field(..., min_length=1, max_length=64, description="工具唯一标识")
    description: str = Field(..., min_length=1, description="工具描述")
    category: ToolCategory = Field(default=ToolCategory.QUERY, description="工具类别")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="风险等级")
    version: str = Field(default="1.0.0", description="工具版本")
    requires_auth: bool = Field(default=True, description="是否需要认证")
    requires_approval: bool = Field(default=False, description="是否需要审批")
    schema: dict[str, Any] = Field(default_factory=dict, description="参数 JSON Schema")
    tags: list[str] = Field(default_factory=list, description="标签列表")


class ToolProtocol:
    """工具协议（Protocol）

    定义工具必须实现的接口。使用 Protocol 而非 ABC 的原因：
    1. 允许鸭子类型，不强制继承
    2. 与 LangChain 等框架的工具接口兼容
    3. 零运行时开销

    【Protocol 使用要点】
    - @runtime_check 装饰器可启用运行时检查（可选）
    - 方法签名必须与协议一致
    - 私有方法（_开头）不参与协议检查

    Example:
        实现协议的工具：
        ```python
        class QueryOrderTool:
            @property
            def metadata(self) -> ToolMetadata:
                return ToolMetadata(name="query_order", ...)

            async def execute(self, arguments: dict) -> ToolResult:
                # 实现查询逻辑
                return ToolResult(success=True, data={...})
        ```
    """

    @property
    def metadata(self) -> ToolMetadata:
        """获取工具元数据

        Returns:
            ToolMetadata: 工具元信息，包含名称、描述、风险等级等
        """
        ...

    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """执行工具

        Args:
            arguments: 工具参数，符合 metadata.schema 定义

        Returns:
            ToolResult: 执行结果

        Raises:
            ValidationError: 参数校验失败
            ToolExecutionError: 执行失败
        """
        ...

    async def validate_arguments(self, arguments: dict[str, Any]) -> bool:
        """校验参数

        Args:
            arguments: 待校验的参数

        Returns:
            bool: 参数是否有效

        Note:
            默认实现使用 JSON Schema 校验，
            子类可覆盖实现自定义校验逻辑。
        """
        ...


@dataclass
class BaseTool(ABC):
    """工具抽象基类

    提供工具的通用实现，减少重复代码。
    继承此类可快速实现新工具。

    【使用场景】
    - 需要通用功能（如参数校验、日志）
    - 需要继承而非组合
    - 需要运行时类型检查

    【ABC vs Protocol】
    - 使用 ABC：需要复用代码、需要运行时检查
    - 使用 Protocol：只需接口定义、与第三方代码集成

    Attributes:
        _metadata: 工具元数据（延迟初始化）

    Example:
        ```python
        class QueryOrderTool(BaseTool):
            def _build_metadata(self) -> ToolMetadata:
                return ToolMetadata(
                    name="query_order_status",
                    description="查询订单状态",
                    category=ToolCategory.QUERY,
                    risk_level=RiskLevel.LOW,
                )

            async def execute(self, arguments: dict) -> ToolResult:
                order_id = arguments.get("order_id")
                # 查询逻辑...
                return ToolResult(success=True, data={"status": "completed"})
        ```
    """

    _metadata: ToolMetadata | None = field(default=None, init=False)

    @property
    def metadata(self) -> ToolMetadata:
        """获取工具元数据（延迟初始化）"""
        if self._metadata is None:
            self._metadata = self._build_metadata()
        return self._metadata

    @abstractmethod
    def _build_metadata(self) -> ToolMetadata:
        """构建工具元数据

        子类必须实现此方法，定义工具元信息。

        Returns:
            ToolMetadata: 工具元数据
        """
        ...

    @abstractmethod
    async def execute(self, arguments: dict[str, Any]) -> ToolResult:
        """执行工具（子类实现）

        Args:
            arguments: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        ...

    async def validate_arguments(self, arguments: dict[str, Any]) -> bool:
        """校验参数（使用 JSON Schema）

        默认实现使用 metadata.schema 进行校验。
        子类可覆盖实现自定义校验逻辑。

        Args:
            arguments: 待校验的参数

        Returns:
            bool: 参数是否有效
        """
        import jsonschema

        schema = self.metadata.schema
        if not schema:
            return True

        try:
            jsonschema.validate(arguments, schema)
            return True
        except jsonschema.ValidationError:
            return False

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.metadata.name})"


class ToolExecutionError(Exception):
    """工具执行错误

    统一的工具执行异常，包含错误码和上下文信息。

    Attributes:
        tool_name: 工具名称
        error_code: 错误码
        details: 错误详情
    """

    def __init__(
        self,
        message: str,
        tool_name: str,
        error_code: str = "ERR_TOOL_EXECUTION_FAILED",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.tool_name = tool_name
        self.error_code = error_code
        self.details = details or {}
