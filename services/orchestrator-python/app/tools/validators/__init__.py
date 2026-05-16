"""工具参数校验模块 - 防止恶意输入

【模块架构】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

                    ┌─────────────────────────────────┐
                    │         tool_call_node          │
                    │      (LangGraph 节点)          │
                    └─────────────────┬───────────────┘
                                      │ tool_calls
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          VALIDATORS MODULE                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     JSONSchemaValidator                             │   │
│  │                                                                     │   │
│  │  输入: tool_definition (JSON Schema)                                │   │
│  │        arguments (用户传入参数)                                      │   │
│  │                                                                     │   │
│  │  校验规则:                                                          │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ type 检查    │  │ required     │  │ bounds       │              │   │
│  │  │ string/int   │  │ 必填字段     │  │ min/max      │              │   │
│  │  │ object/array │  │              │  │              │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │   │
│  │  │ pattern      │  │ enum         │  │ format       │              │   │
│  │  │ 正则匹配     │  │ 枚举值       │  │ 日期/邮箱    │              │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘              │   │
│  │                                                                     │   │
│  │  输出: ValidationResult                                            │   │
│  │        is_valid: bool                                              │   │
│  │        errors: list[str]                                           │   │
│  │        defaults_filled: dict (填充后的参数)                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                                      ▼                                      │
│                    ┌─────────────────────────────────┐                      │
│                    │      ToolBus Service            │                      │
│                    │   (接收校验后的安全参数)         │                      │
│                    └─────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘

【安全防护位置】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

参数校验是 S-AGENT-06（五层鉴权）的第一层:

┌─────────────────────────────────────────────────────────────────────────────┐
│                              五层鉴权链                                     │
│                                                                             │
│  Layer 1: 参数校验      ← validators 模块 (本模块)                          │
│           │                                                                 │
│           ▼ 检查参数类型、必填字段、边界值                                  │
│  Layer 2: RBAC          ← Gateway 权限校验                                  │
│           │                                                                 │
│           ▼ 检查用户角色是否有权限                                          │
│  Layer 3: 租户隔离      ← TenantContext                                     │
│           │                                                                 │
│           ▼ 检查数据是否属于当前租户                                        │
│  Layer 4: ABAC          ← Governance                                        │
│           │                                                                 │
│           ▼ 检查资源属性是否满足条件                                        │
│  Layer 5: 风险等级      ← ToolBus                                           │
│           │                                                                 │
│           ▼ 高风险操作需要审批                                              │
└─────────────────────────────────────────────────────────────────────────────┘

【子模块职责】
┌────────────────────┬──────────────────────────────────────────────────────────────┐
│ 子模块              │ 职责描述                                                      │
├────────────────────┼──────────────────────────────────────────────────────────────┤
│ json_schema_       │ JSON Schema 校验器：                                          │
│ validator          │ • type 检查 (string/integer/boolean/object/array)            │
│                    │ • required 必填字段校验                                       │
│                    │ • min/max/maxLength/minLength 边界值校验                      │
│                    │ • pattern 正则表达式校验                                      │
│                    │ • enum 枚举值校验                                             │
│                    │ • format 特殊格式校验 (date-time/email/uri)                  │
│                    │ • default 值填充                                              │
└────────────────────┴──────────────────────────────────────────────────────────────┘

【核心组件】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. JSONSchemaValidator
   ━━━━━━━━━━━━━━━━━━━━━━
   - 基于 jsonschema 库实现完整 JSON Schema Draft-07 支持
   - 支持的工具定义格式: OpenAI Function Calling 格式
   - 核心方法:
     • validate(): 校验参数，返回 ValidationResult
     • fill_defaults(): 填充默认值
     • create_from_tool_definition(): 从工具定义创建校验器

2. ValidationResult
   ━━━━━━━━━━━━━━━━━━━━━━
   - is_valid: 校验是否通过
   - errors: 错误信息列表
   - defaults_filled: 填充后的参数（包含 default 值）
   - warnings: 警告信息（如未识别的字段）

【defaults 填充机制】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

JSON Schema 允许定义 default 值，校验器自动填充:

```json
{
  "type": "object",
  "properties": {
    "page_size": {
      "type": "integer",
      "default": 20,
      "minimum": 1,
      "maximum": 100
    }
  }
}
```

用户传入: {"page_size": null}
填充后: {"page_size": 20}

【使用示例】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# 1. 创建校验器
from app.tools.validators import JSONSchemaValidator, ValidationResult

tool_schema = {
    "type": "object",
    "properties": {
        "order_id": {
            "type": "string",
            "description": "订单号",
            "minLength": 1,
            "maxLength": 32
        },
        "page_size": {
            "type": "integer",
            "default": 20,
            "minimum": 1,
            "maximum": 100
        }
    },
    "required": ["order_id"]
}

validator = JSONSchemaValidator(tool_schema)

# 2. 校验参数
result: ValidationResult = validator.validate({"order_id": "ORD-123"})

if result.is_valid:
    # 使用填充后的参数（包含 default 值）
    arguments = result.defaults_filled
    print(arguments)  # {"order_id": "ORD-123", "page_size": 20}
else:
    print(f"校验失败: {result.errors}")

# 3. 使用便捷函数
from app.tools.validators import validate_tool_arguments

is_valid, errors = validate_tool_arguments(
    tool_definition=tool_schema,
    arguments={"order_id": "ORD-123"}
)

# 4. 从工具定义创建校验器
from app.tools.validators import create_validator_from_tool_definition

validator = create_validator_from_tool_definition(
    tool_definition={
        "name": "query_order",
        "description": "查询订单",
        "parameters": tool_schema
    }
)

# 5. 在 tool_call_node 中集成
# (实际代码见 app/graph/nodes/tool_call.py)
from app.tools.validators import JSONSchemaValidator

async def validate_before_execution(tool, arguments):
    validator = JSONSchemaValidator(tool.metadata.schema)
    result = validator.validate(arguments)

    if not result.is_valid:
        raise ToolValidationError(
            tool_name=tool.metadata.name,
            reason=result.errors[0]
        )

    # 使用填充后的参数执行
    return await tool.execute(result.defaults_filled)

# 6. 复杂 Schema 校验示例
complex_schema = {
    "type": "object",
    "properties": {
        "email": {
            "type": "string",
            "format": "email"
        },
        "status": {
            "type": "string",
            "enum": ["pending", "completed", "cancelled"]
        },
        "created_at": {
            "type": "string",
            "format": "date-time"
        },
        "amount": {
            "type": "number",
            "minimum": 0,
            "exclusiveMaximum": 1000000
        }
    },
    "required": ["email", "status"]
}

validator = JSONSchemaValidator(complex_schema)
result = validator.validate({
    "email": "test@example.com",
    "status": "pending"
})
```

【安全防护案例】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

```python
# 案例 1: 防止 SQL 注入参数
# Schema 定义限制参数格式
dangerous_input = {
    "order_id": "ORD-123'; DROP TABLE orders; --"
}

# Schema 限制长度和格式
schema = {
    "type": "object",
    "properties": {
        "order_id": {
            "type": "string",
            "pattern": "^ORD-[A-Z0-9]+$",  # 只允许特定格式
            "maxLength": 32
        }
    }
}

validator = JSONSchemaValidator(schema)
result = validator.validate(dangerous_input)
# result.is_valid = False (不符合 pattern)

# 案例 2: 防止越权访问
# Schema 强制要求 tenant_id
schema = {
    "type": "object",
    "properties": {
        "order_id": {"type": "string"},
        "tenant_id": {"type": "string"}  # 必须传入租户 ID
    },
    "required": ["order_id", "tenant_id"]
}

# 案例 3: 防止数值溢出
schema = {
    "type": "object",
    "properties": {
        "amount": {
            "type": "integer",
            "minimum": 1,
            "maximum": 1000000  # 上限 100 万
        }
    }
}

validator = JSONSchemaValidator(schema)
result = validator.validate({"amount": 999999999})
# result.is_valid = False (超过 maximum)
```

【技术选型】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

选择 jsonschema 库的原因:
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
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【参考】
- JSON Schema Draft-07: https://json-schema.org/specification-links.html
- jsonschema 库文档: https://python-jsonschema.readthedocs.io/
- OpenAI Function Calling: https://platform.openai.com/docs/guides/function-calling
"""

from app.tools.validators.json_schema_validator import (
    JSONSchemaValidator,
    ValidationResult,
    create_validator_from_tool_definition,
    validate_tool_arguments,
)

__all__ = [
    "JSONSchemaValidator",
    "ValidationResult",
    "validate_tool_arguments",
    "create_validator_from_tool_definition",
]
