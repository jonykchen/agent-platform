"""JSON Schema 校验器

对工具调用参数进行严格校验，防止恶意输入。
使用 jsonschema 库实现完整 JSON Schema Draft-07 支持。

【核心概念】参数校验在 Agent 安全中的位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

参数校验是 S-AGENT-06（工具调用鉴权链）的第一步：
- 防止恶意参数注入（如 SQL 注入、命令注入）
- 防止参数类型错误导致下游服务异常
- 提供友好的错误提示，减少无效调用

【技术选型】JSON Schema 校验方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ jsonschema (选择)  │ • 完整 Draft-07 支持        │ • 依赖（但很轻量）          │
│                    │ • 标准化                    │                              │
│                    │ • 社区活跃                  │                              │
│                    │ • 错误信息详细              │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ Pydantic 验证      │ • 与 Pydantic 模型集成      │ • Schema 转换复杂          │
│                    │ • 性能好                    │ • 不支持部分 Draft-07 特性  │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 手动类型检查       │ • 无依赖                    │ • 实现复杂                  │
│                    │                             │ • 难以覆盖所有校验规则      │
│                    │                             │ • 代码冗长                  │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择 jsonschema 的原因】
1. 工具定义已经是 OpenAI 格式的 JSON Schema，直接使用
2. 完整支持 required、minimum/maximum、pattern、enum 等
3. 提供 defaults 填充功能，简化参数传递

【defaults 填充机制】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JSON Schema 允许定义 default 值：

{
  "type": "object",
  "properties": {
    "page_size": {
      "type": "integer",
      "default": 20
    }
  }
}

当用户未提供 page_size 时，校验器自动填充默认值。
这减少了 LLM 必须输出的参数数量，提高成功率。

【错误路径定位】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

校验失败时，返回错误路径：

{
  "valid": false,
  "errors": ["order_id: does not match pattern ^ORD-[\\w-]+$"]
}

路径格式：field.subfield（如 user.address.city）

【设计原则】
- 校验失败返回详细错误信息，便于调试
- 支持自定义错误消息（tool 定义中可指定）
- 校验结果包含具体的失败路径

【参考】
- S-AGENT-06: 工具调用必须经过鉴权
- JSON Schema Draft-07: https://json-schema.org/draft-07/json-schema-validation.html
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()

# 尝试导入 jsonschema
try:
    import jsonschema
    from jsonschema import Draft7Validator, validators
    from jsonschema.exceptions import ValidationError as JsonSchemaError

    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    logger.warning("jsonschema_not_available", fallback="basic_type_check")


@dataclass
class ValidationResult:
    """校验结果

    Attributes:
        valid: 是否通过校验
        errors: 错误列表
        data: 校验后的数据（可能经过 defaults 填充）
    """

    valid: bool
    errors: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "data": self.data,
        }


class JSONSchemaValidator:
    """JSON Schema 校验器

    支持完整 JSON Schema Draft-07 规范。

    使用示例：
        validator = JSONSchemaValidator(schema)
        result = validator.validate(arguments)
        if not result.valid:
            raise ToolValidationError(result.errors)
    """

    def __init__(self, schema: dict[str, Any], use_defaults: bool = True):
        """初始化校验器

        Args:
            schema: JSON Schema 定义
            use_defaults: 是否自动填充 default 值
        """
        self.schema = schema
        self.use_defaults = use_defaults
        self._validator = None

        if JSONSCHEMA_AVAILABLE:
            # 创建支持 defaults 的 validator
            if use_defaults:
                self._validator = self._create_validator_with_defaults()
            else:
                self._validator = Draft7Validator(schema)

    def _create_validator_with_defaults(self):
        """创建支持自动填充 defaults 的 validator"""

        def set_defaults(validator_class):
            def populate_defaults(validator, properties, instance, schema):
                if not isinstance(instance, dict):
                    return
                for property_name, subschema in properties.items():
                    if "default" in subschema and property_name not in instance:
                        instance[property_name] = subschema["default"]

                for error in validator_class.VALIDATORS["properties"](
                    validator,
                    properties,
                    instance,
                    schema,
                ):
                    yield error

            return validators.extend(
                validator_class,
                {"properties": populate_defaults},
            )

        DefaultValidator = set_defaults(Draft7Validator)
        return DefaultValidator(self.schema)

    def validate(self, data: dict[str, Any]) -> ValidationResult:
        """校验数据

        Args:
            data: 待校验的数据字典

        Returns:
            ValidationResult 对象
        """
        if not JSONSCHEMA_AVAILABLE:
            return self._basic_validate(data)

        errors: list[str] = []

        # 复制数据以避免修改原始值
        data_copy = json.loads(json.dumps(data))

        try:
            self._validator.validate(data_copy)
            return ValidationResult(valid=True, data=data_copy)
        except JsonSchemaError as e:
            # 构建友好的错误信息
            path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
            error_msg = f"{path}: {e.message}"
            errors.append(error_msg)

            logger.warning(
                "json_schema_validation_failed",
                path=path,
                message=e.message,
                validator=e.validator,
            )

            return ValidationResult(valid=False, errors=errors, data=data)

        except json.JSONDecodeError as e:
            return ValidationResult(
                valid=False,
                errors=[f"JSON 解析错误: {e.msg}"],
                data=data,
            )

    def _basic_validate(self, data: dict[str, Any]) -> ValidationResult:
        """基础类型校验（无 jsonschema 时的回退）

        Args:
            data: 待校验的数据

        Returns:
            ValidationResult 对象
        """
        errors: list[str] = []

        if not isinstance(data, dict):
            return ValidationResult(
                valid=False,
                errors=["参数必须是字典类型"],
                data=data,
            )

        # 检查必填字段
        required = self.schema.get("required", [])
        for field_name in required:
            if field_name not in data:
                errors.append(f"缺少必填字段: {field_name}")

        # 检查字段类型
        properties = self.schema.get("properties", {})
        for field_name, value in data.items():
            if field_name in properties:
                field_schema = properties[field_name]
                expected_type = field_schema.get("type")

                if expected_type and not self._check_type(value, expected_type):
                    errors.append(f"字段 '{field_name}' 类型错误: 期望 {expected_type}，实际 {type(value).__name__}")

        # 填充 defaults
        if self.use_defaults:
            for field_name, field_schema in properties.items():
                if "default" in field_schema and field_name not in data:
                    data[field_name] = field_schema["default"]

        return ValidationResult(valid=len(errors) == 0, errors=errors, data=data)

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """检查值类型

        Args:
            value: 待检查的值
            expected_type: JSON Schema 类型字符串

        Returns:
            类型是否匹配
        """
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None),
        }

        expected = type_mapping.get(expected_type)
        if expected is None:
            return True  # 未知类型，放行

        return isinstance(value, expected)

    def get_schema(self) -> dict[str, Any]:
        """获取当前的 JSON Schema"""
        return self.schema.copy()


def validate_tool_arguments(
    tool_name: str,
    arguments: dict[str, Any],
    schema: dict[str, Any],
) -> ValidationResult:
    """便捷函数：校验工具参数

    Args:
        tool_name: 工具名称（用于日志）
        arguments: 待校验的参数
        schema: JSON Schema 定义

    Returns:
        ValidationResult 对象
    """
    validator = JSONSchemaValidator(schema)
    result = validator.validate(arguments)

    if not result.valid:
        logger.warning(
            "tool_arguments_validation_failed",
            tool_name=tool_name,
            errors=result.errors,
        )

    return result


def create_validator_from_tool_definition(tool_def: dict[str, Any]) -> JSONSchemaValidator:
    """从工具定义创建校验器

    Args:
        tool_def: OpenAI 格式的工具定义，包含 function.parameters

    Returns:
        JSONSchemaValidator 实例
    """
    # OpenAI 工具定义结构
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "...",
    #         "parameters": {...}  # JSON Schema
    #     }
    # }

    function = tool_def.get("function", {})
    parameters = function.get("parameters", {})

    return JSONSchemaValidator(parameters)
