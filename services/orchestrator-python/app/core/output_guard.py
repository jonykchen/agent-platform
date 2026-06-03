"""输出泄露检测 (S-AGENT-04/05)

检测 LLM 输出是否包含：
- 系统提示原文
- 工具定义
- 其他用户数据
- JSON 格式错误

【核心概念】输出泄露风险
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LLM 可能因 Prompt 注入或模型行为泄露敏感信息：
- 泄露 System Prompt：暴露 Agent 行为规则
- 泄露工具定义：暴露系统架构
- 泄露其他用户数据：跨用户数据泄露（严重安全问题）
- 输出 JSON 格式错误：导致前端解析失败

【防护层级】L4 层防御
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

本系统采用四层防护：

┌─────────────────────────────────────────────────────────────────────────────┐
│                          Agent 安全防护层级                                  │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │  L1: 输入长度限制 (S-AGENT-03)                                    │    │
│   │  - 用户输入 ≤ 8000 tokens                                         │    │
│   │  - 防止超长输入攻击                                               │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                          │                                                  │
│                          ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │  L2: Prompt 注入检测 (S-AGENT-01/02, PromptInjectionGuard)        │    │
│   │  - 检测注入模式                                                   │    │
│   │  - 移除注入内容                                                   │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                          │                                                  │
│                          ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │  L3: 工具调用鉴权 (S-AGENT-06/07)                                 │    │
│   │  - 五层权限检查                                                   │    │
│   │  - 高风险操作审批                                                 │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                          │                                                  │
│                          ▼                                                  │
│   ┌──────────────────────────────────────────────────────────────────┐    │
│   │  L4: 输出泄露检测 (S-AGENT-04/05, OutputLeakageGuard) ← 本模块    │    │
│   │  - 扫描输出内容                                                   │    │
│   │  - 清理泄露信息                                                   │    │
│   └──────────────────────────────────────────────────────────────────┘    │
│                          │                                                  │
│                          ▼                                                  │
│                      安全输出给用户                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

与 PromptInjectionGuard 形成闭环防护：
- PromptInjectionGuard: 输入检测（L2）
- OutputLeakageGuard: 输出检测（L4）

【检测模式】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 系统提示泄露模式：
   - "system prompt:", "your instructions are"
   - "你是一个AI助手", "你的任务是"

2. 工具定义泄露模式：
   - "tool_definition", "available tools"
   - "工具定义", "可用工具"

3. JSON 格式错误：
   - 不完整的 JSON 对象
   - 无法解析的 JSON 数组

【处理策略】
- allow: 安全，直接输出
- warn: 有风险但可控，记录日志
- sanitize: 需清理，移除泄露内容后输出

【设计原则】
L4 层防御：在 LLM 输出返回给用户前，扫描是否存在敏感信息泄露。
与 PromptInjectionGuard 形成闭环防护：
- PromptInjectionGuard: 输入检测
- OutputLeakageGuard: 输出检测
"""

import json
import re
from typing import Optional

import structlog

logger = structlog.get_logger()


class OutputLeakageGuard:
    """输出泄露检测器

    检测 LLM 输出中可能存在的敏感信息泄露：
    1. 系统提示泄露
    2. 工具定义泄露
    3. JSON 格式错误
    4. 其他用户数据泄露
    """

    # 泄露模式 - 系统提示相关
    SYSTEM_PROMPT_PATTERNS = [
        r"system prompt[:：]",
        r"you are (a|an) (ai|assistant|language model)",
        r"your instructions (are|is)",
        r"your task is to",
        r"你是一个(ai|助手|语言模型)",
        r"你的指令是",
        r"你的任务是",
    ]

    # 泄露模式 - 工具定义相关
    TOOL_DEFINITION_PATTERNS = [
        r"tool[_-]?definition",
        r"function[_-]?call",
        r"action[_-]?input",
        r"工具定义",
        r"函数调用",
        r"tool_calls?\s*:",
        r"available tools",
        r"可用工具",
    ]

    # JSON 格式错误模式
    JSON_ERROR_PATTERNS = [
        r'\{\s*"[^"]+"\s*:\s*[^}]*\}(?!\s*[,\]}])',  # 不完整 JSON
        r'\[\s*\{[^}]*\}(?!\s*[,\]])',  # 不完整数组
    ]

    def __init__(
        self,
        json_validation_threshold: float = 0.995,
        enable_json_validation: bool = True,
    ):
        self.json_validation_threshold = json_validation_threshold
        self.enable_json_validation = enable_json_validation

        # 预编译正则表达式
        self._system_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.SYSTEM_PROMPT_PATTERNS
        ]
        self._tool_regexes = [
            re.compile(p, re.IGNORECASE) for p in self.TOOL_DEFINITION_PATTERNS
        ]

    def scan(self, output: str, context: Optional[dict] = None) -> dict:
        """扫描输出检测泄露

        Args:
            output: LLM 输出文本
            context: 上下文信息（用于日志）
                - session_id: 当前会话 ID
                - tenant_id: 租户 ID
                - request_id: 请求 ID

        Returns:
            {
                "safe": bool,
                "leakage_detected": bool,
                "leakage_type": str | None,  # system_prompt / tool_definition / user_data / cross_session
                "matched_patterns": list[str],
                "json_valid": bool,
                "action": str  # allow / warn / sanitize
            }
        """
        result = {
            "safe": True,
            "leakage_detected": False,
            "leakage_type": None,
            "matched_patterns": [],
            "json_valid": True,
            "action": "allow",
        }

        if not output:
            return result

        # 1. 检测系统提示泄露
        for regex in self._system_regexes:
            match = regex.search(output)
            if match:
                result["matched_patterns"].append(f"system_prompt:{match.group()}")
                result["leakage_type"] = "system_prompt"

        # 2. 检测工具定义泄露
        for regex in self._tool_regexes:
            match = regex.search(output)
            if match:
                result["matched_patterns"].append(f"tool_definition:{match.group()}")
                result["leakage_type"] = "tool_definition"

        # 3. JSON 格式校验
        if self.enable_json_validation:
            result["json_valid"] = self._validate_json_output(output)
            if not result["json_valid"]:
                result["matched_patterns"].append("json_format_error")

        # 4. 跨会话数据泄露检测（新增）
        if context and self._check_cross_session_leak(output, context):
            result["matched_patterns"].append("cross_session_data")
            if not result["leakage_type"]:
                result["leakage_type"] = "cross_session_data"

        # 决策
        if result["matched_patterns"]:
            result["leakage_detected"] = True
            result["safe"] = False

            # 根据泄露类型决定动作
            if result["leakage_type"] in ("system_prompt", "tool_definition", "cross_session_data"):
                result["action"] = "sanitize"
            elif not result["json_valid"]:
                result["action"] = "warn"
            else:
                result["action"] = "warn"

            logger.warning(
                "Output leakage detected",
                leakage_type=result["leakage_type"],
                matched_patterns=result["matched_patterns"],
                action=result["action"],
                context=context,
            )

        return result

    def _check_cross_session_leak(self, output: str, context: dict) -> bool:
        """检测输出是否包含其他会话的数据

        【安全考虑】
        防止 LLM 输出中泄露其他用户或会话的数据。
        这可能是由于：
        1. 模型训练数据泄露
        2. 提示词注入攻击
        3. 缓存污染

        Args:
            output: LLM 输出文本
            context: 上下文信息

        Returns:
            是否检测到跨会话泄露
        """
        current_session = context.get("session_id")
        if not current_session:
            return False

        # 检测会话 ID 格式
        session_pattern = r"sess_[a-zA-Z0-9]{16}_[a-zA-Z0-9]+"
        found_sessions = re.findall(session_pattern, output)

        for sess in found_sessions:
            if sess != current_session:
                logger.warning(
                    "cross_session_data_detected",
                    current_session=current_session,
                    leaked_session=sess,
                    request_id=context.get("request_id"),
                )
                return True

        # 检测其他用户 ID 格式（如果输出包含明确的用户 ID）
        current_user = context.get("user_id")
        if current_user:
            user_pattern = r"user_[a-zA-Z0-9]+"
            found_users = re.findall(user_pattern, output)
            for user in found_users:
                if user != current_user:
                    logger.warning(
                        "cross_user_data_detected",
                        current_user=current_user,
                        leaked_user=user,
                        request_id=context.get("request_id"),
                    )
                    return True

        return False

    def _validate_json_output(self, output: str) -> bool:
        """校验 JSON 输出完整性

        检查输出中是否包含有效的 JSON 结构。
        如果输出预期是 JSON 格式，验证其合法性。
        """
        # 尝试提取 JSON 块
        json_patterns = [
            r'\{[^{}]*\}',  # 单层 JSON 对象
            r'\[[^\[\]]*\]',  # 单层 JSON 数组
        ]

        for pattern in json_patterns:
            matches = re.findall(pattern, output, re.DOTALL)
            for match in matches:
                try:
                    json.loads(match)
                except json.JSONDecodeError:
                    return False

        return True

    def sanitize(self, output: str, context: Optional[dict] = None) -> str:
        """清理泄露内容

        Args:
            output: LLM 输出文本
            context: 上下文信息

        Returns:
            清理后的文本
        """
        scan_result = self.scan(output, context)

        if scan_result["action"] == "allow":
            return output

        if scan_result["action"] == "sanitize":
            sanitized = output

            # 移除匹配的泄露内容
            for pattern in scan_result["matched_patterns"]:
                if ":" in pattern:
                    _, matched_text = pattern.split(":", 1)
                    sanitized = sanitized.replace(matched_text, "[REDACTED]")

            logger.info(
                "Output sanitized",
                original_length=len(output),
                sanitized_length=len(sanitized),
                context=context,
            )
            return sanitized

        return output

    def validate_json_strict(self, output: str) -> tuple[bool, Optional[str]]:
        """严格 JSON 校验

        尝试将整个输出解析为 JSON，返回校验结果和错误信息。

        Returns:
            (is_valid, error_message)
        """
        try:
            json.loads(output)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"JSON parse error at line {e.lineno}, column {e.colno}: {e.msg}"


class OutputLeakageError(Exception):
    """输出泄露错误"""

    def __init__(self, message: str, leakage_type: str, matched_patterns: list[str]):
        self.message = message
        self.leakage_type = leakage_type
        self.matched_patterns = matched_patterns
        super().__init__(message)


# 全局实例
output_guard = OutputLeakageGuard()
