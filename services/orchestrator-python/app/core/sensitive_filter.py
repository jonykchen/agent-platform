"""敏感信息脱敏过滤器

用于日志输出前自动脱敏：
- 手机号：保留前 3 后 4
- 身份证：保留前 6 后 4
- 银行卡：保留后 4
- API Key：保留前 4
- JWT Token：保留前 8

【核心概念】日志安全与 G-SEC-02
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

日志是审计和调试的重要工具，但也可能泄露敏感信息：
- 用户手机号、身份证号
- API Key、JWT Token
- 密码、银行卡号

G-SEC-02 规定：敏感信息必须脱敏，包括日志输出。

【技术选型】structlog Processor 原理
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

structlog 使用 Processor 链处理日志：

┌─────────────────────────────────────────────────────────────────────────────┐
│                          structlog 处理链                                   │
│                                                                             │
│   log.info("user_login", phone="13812345678")                              │
│                          │                                                  │
│                          ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │  Processor 1: merge_contextvars                                   │    │
│   │  - 合入 contextvars（如 request_id）                              │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                          │                                                  │
│                          ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │  Processor 2: SensitiveDataProcessor (本模块)                     │    │
│   │  - 扫描并脱敏敏感信息                                              │    │
│   │  - phone="13812345678" → phone="138****5678"                      │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                          │                                                  │
│                          ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │  Processor 3: JSONRenderer                                        │    │
│   │  - 输出 JSON 格式日志                                              │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                          │                                                  │
│                          ▼                                                  │
│   {"event": "user_login", "phone": "138****5678", "request_id": "..."}    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

【Processor 链的优势】
- 模块化：每个 Processor 只处理一个任务
- 可插拔：按需添加或移除
- 性能可控：异步处理不影响主逻辑

【脱敏规则】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| 数据类型     | 脱敏规则             | 示例                        |
|-------------|---------------------|----------------------------|
| 手机号       | 前3后4，中间****    | 13812345678 → 138****5678  |
| 身份证       | 前6后4，中间****    | 370102199001011234 → ...   |
| 银行卡       | 后4，前****         | 6225881234567890 → ****7890|
| 邮箱         | 字母+***@域名      | zhangsan@example → z***@...|
| API Key     | 前4，后...          | sk-abc123... → sk-a...     |
| JWT Token   | 前8，后...          | eyJhbG... → eyJhbG...      |

【性能优化】
- 预编译正则表达式：避免每次重新编译
- 使用 dataclass：减少对象创建开销
- 设置 max_length：截断超长字符串，防止日志爆炸

【设计原则】
- 作为 structlog Processor 使用
- 支持自定义字段和模式
- 性能优化：预编译正则表达式

【参考】
- G-SEC-02: 敏感信息必须脱敏
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

import structlog


@dataclass
class SensitivePattern:
    """敏感信息模式定义

    Attributes:
        name: 模式名称
        pattern: 正则表达式
        mask: 脱敏函数，接收 match 对象返回脱敏后的字符串
    """

    name: str
    pattern: re.Pattern
    mask: Callable[[re.Match], str]


def mask_phone(match: re.Match) -> str:
    """手机号脱敏：保留前 3 后 4"""
    text = match.group()
    return f"{text[:3]}****{text[-4:]}"


def mask_id_card(match: re.Match) -> str:
    """身份证脱敏：保留前 6 后 4"""
    text = match.group()
    return f"{text[:6]}********{text[-4:]}"


def mask_bank_card(match: re.Match) -> str:
    """银行卡脱敏：保留后 4"""
    text = match.group()
    return f"****{text[-4:]}"


def mask_email(match: re.Match) -> str:
    """邮箱脱敏：首字母 + *** @域名"""
    text = match.group()
    if "@" in text:
        name, domain = text.split("@", 1)
        masked_name = f"{name[0]}***" if len(name) > 1 else "***"
        return f"{masked_name}@{domain}"
    return "***"


def mask_api_key(match: re.Match) -> str:
    """API Key 脱敏：保留前 4"""
    text = match.group()
    return f"{text[:4]}...{'*' * (len(text) - 4)}"


def mask_jwt(match: re.Match) -> str:
    """JWT Token 脱敏：保留前 8"""
    text = match.group()
    return f"{text[:8]}..."


def mask_password(match: re.Match) -> str:
    """密码字段：完全隐藏"""
    return "********"


# 默认敏感信息模式
DEFAULT_PATTERNS: list[SensitivePattern] = [
    # 手机号（中国大陆）
    SensitivePattern(
        name="phone",
        pattern=re.compile(r"1[3-9]\d{9}"),
        mask=mask_phone,
    ),
    # 身份证（18位）
    SensitivePattern(
        name="id_card",
        pattern=re.compile(r"\d{17}[\dXx]"),
        mask=mask_id_card,
    ),
    # 银行卡（16-19位）
    SensitivePattern(
        name="bank_card",
        pattern=re.compile(r"\d{16,19}"),
        mask=mask_bank_card,
    ),
    # 邮箱
    SensitivePattern(
        name="email",
        pattern=re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        mask=mask_email,
    ),
    # API Key（常见格式）
    SensitivePattern(
        name="api_key",
        pattern=re.compile(r"(?:sk-|api[_-]?key[_-]?)[a-zA-Z0-9]{20,}", re.IGNORECASE),
        mask=mask_api_key,
    ),
    # JWT Token
    SensitivePattern(
        name="jwt",
        pattern=re.compile(r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"),
        mask=mask_jwt,
    ),
]

# 敏感字段名（这些字段的值会被完全隐藏）
SENSITIVE_FIELD_NAMES: set[str] = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth",
    "credential",
    "private_key",
    "privatekey",
}


class SensitiveDataProcessor(structlog.types.Processor):
    """敏感信息脱敏处理器

    作为 structlog Processor 使用，自动过滤日志中的敏感信息。

    使用示例：
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                SensitiveDataProcessor(),
                structlog.processors.JSONRenderer(),
            ]
        )
    """

    def __init__(
        self,
        patterns: list[SensitivePattern] | None = None,
        sensitive_fields: set[str] | None = None,
        max_length: int = 500,
    ):
        """初始化处理器

        Args:
            patterns: 敏感信息模式列表（默认使用 DEFAULT_PATTERNS）
            sensitive_fields: 敏感字段名集合（默认使用 SENSITIVE_FIELD_NAMES）
            max_length: 字符串最大长度，超长截断
        """
        self.patterns = patterns or DEFAULT_PATTERNS
        self.sensitive_fields = sensitive_fields or SENSITIVE_FIELD_NAMES
        self.max_length = max_length

    def __call__(
        self,
        logger: structlog.typing.WrappedLogger,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        """处理日志事件

        Args:
            logger: structlog logger
            method_name: 日志方法名
            event_dict: 日志事件字典

        Returns:
            处理后的日志事件字典
        """
        return self._process_dict(event_dict)

    def _process_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """处理字典数据

        Args:
            data: 待处理的字典

        Returns:
            处理后的字典
        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            result[key] = self._process_value(key, value)
        return result

    def _process_value(self, key: str, value: Any) -> Any:
        """处理值

        Args:
            key: 字段名
            value: 字段值

        Returns:
            处理后的值
        """
        # 敏感字段名直接隐藏
        if key.lower() in self.sensitive_fields:
            return "********"

        # 字符串处理
        if isinstance(value, str):
            return self._mask_string(value)

        # 递归处理嵌套字典
        if isinstance(value, dict):
            return self._process_dict(value)

        # 递归处理列表
        if isinstance(value, list):
            return [self._process_value(str(i), item) for i, item in enumerate(value)]

        return value

    def _mask_string(self, text: str) -> str:
        """对字符串进行脱敏

        Args:
            text: 原始字符串

        Returns:
            脱敏后的字符串
        """
        if not text:
            return text

        result = text
        for pattern in self.patterns:
            result = pattern.pattern.sub(
                lambda m: pattern.mask(m),
                result,
            )

        # 截断超长字符串
        if len(result) > self.max_length:
            result = result[: self.max_length] + "... (truncated)"

        return result


# 便捷函数
def mask_sensitive(text: str) -> str:
    """便捷函数：对文本进行脱敏

    Args:
        text: 原始文本

    Returns:
        脱敏后的文本
    """
    processor = SensitiveDataProcessor()
    return processor._mask_string(text)
