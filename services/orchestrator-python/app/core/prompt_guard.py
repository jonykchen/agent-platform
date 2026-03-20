"""Prompt 注入防护 (S-02)

检测和阻止 Prompt 注入攻击，支持中文模式。
"""

import re
from typing import Optional

import structlog

logger = structlog.get_logger()


class PromptInjectionGuard:
    """Prompt 注入防护器

    检测常见 Prompt 注入模式：
    - 角色扮演注入
    - 系统指令覆盖
    - 输出控制劫持
    - 中文变体攻击
    """

    # 英文注入模式
    ENGLISH_PATTERNS = [
        r"ignore (all|previous|above|below) (instructions|prompts|rules)",
        r"disregard (all|previous|above|below)",
        r"forget (all|previous|above|below)",
        r"(you are|act as|pretend to be|roleplay as) (now|a|an)",
        r"(system|admin|root|developer) (mode|access|privileges)",
        r"(print|output|display|show|write) (your|the|this) (prompt|instructions|system)",
        r"(reveal|disclose|share|tell) (your|the|this) (prompt|instructions|system)",
        r"new (instructions|prompt|directive)",
        r"(stop|halt|pause|end) (generating|outputting|responding)",
    ]

    # 中文注入模式
    CHINESE_PATTERNS = [
        r"忽略(所有|之前|以上|以下|全部)(指令|提示|规则)",
        r"忽略(指令|提示|规则)",
        r" disregard",
        r"忘记(所有|之前|以上|以下|全部)",
        r"(你是|扮演|假装|模拟)(现在|一个)",
        r"(系统|管理员|root|开发者)(模式|权限|访问)",
        r"(输出|打印|显示|展示|写出)(你的|这个|系统)(提示|指令|prompt)",
        r"(泄露|透露|分享|告诉)(你的|这个|系统)(提示|指令|prompt)",
        r"新(指令|提示|命令)",
        r"(停止|暂停|结束)(生成|输出|回复)",
        r"请直接",
        r"不用(思考|分析|判断)",
        r"绕过(检查|限制|规则)",
    ]

    # 高风险关键词
    HIGH_RISK_KEYWORDS = [
        "system prompt",
        "instruction",
        "prompt template",
        "开发者模式",
        "debug mode",
        "admin access",
        "系统提示",
        "原始指令",
        "内部规则",
    ]

    def __init__(
        self,
        max_user_input_length: int = 8000,
        detection_threshold: float = 0.7,
    ):
        self.max_user_input_length = max_user_input_length
        self.detection_threshold = detection_threshold

        # 预编译正则表达式
        self._english_regexes = [re.compile(p, re.IGNORECASE) for p in self.ENGLISH_PATTERNS]
        self._chinese_regexes = [re.compile(p) for p in self.CHINESE_PATTERNS]

    def scan(self, text: str, context: Optional[dict] = None) -> dict:
        """扫描文本检测 Prompt 注入

        Args:
            text: 待检测文本
            context: 上下文信息（用于日志）

        Returns:
            {
                "safe": bool,
                "risk_score": float,
                "matched_patterns": list[str],
                "action": str  # allow / warn / block
            }
        """
        result = {
            "safe": True,
            "risk_score": 0.0,
            "matched_patterns": [],
            "action": "allow",
        }

        if not text:
            return result

        # 长度检查
        if len(text) > self.max_user_input_length:
            result["safe"] = False
            result["risk_score"] = 1.0
            result["matched_patterns"].append("input_length_exceeded")
            result["action"] = "block"
            logger.warning("Prompt injection: input length exceeded", length=len(text), context=context)
            return result

        # 英文模式检测
        for regex in self._english_regexes:
            match = regex.search(text)
            if match:
                result["matched_patterns"].append(match.group())
                result["risk_score"] += 0.3

        # 中文模式检测
        for regex in self._chinese_regexes:
            match = regex.search(text)
            if match:
                result["matched_patterns"].append(match.group())
                result["risk_score"] += 0.35  # 中文模式权重稍高

        # 高风险关键词检测
        lower_text = text.lower()
        for keyword in self.HIGH_RISK_KEYWORDS:
            if keyword.lower() in lower_text:
                result["matched_patterns"].append(keyword)
                result["risk_score"] += 0.2

        # 计算最终风险分数（归一化到 [0, 1]）
        result["risk_score"] = min(result["risk_score"], 1.0)

        # 决策
        if result["risk_score"] >= 0.9:
            result["safe"] = False
            result["action"] = "block"
        elif result["risk_score"] >= self.detection_threshold:
            result["action"] = "warn"
        elif result["risk_score"] > 0.3:
            result["action"] = "log"

        if result["matched_patterns"]:
            logger.warning(
                "Prompt injection detected",
                risk_score=result["risk_score"],
                matched_patterns=result["matched_patterns"],
                action=result["action"],
                context=context,
            )

        return result

    def sanitize(self, text: str, context: Optional[dict] = None) -> str:
        """清理文本，移除注入模式

        Args:
            text: 待清理文本
            context: 上下文信息

        Returns:
            清理后的文本（如果无法安全清理则返回原始文本）
        """
        scan_result = self.scan(text, context)

        if scan_result["action"] == "block":
            raise PromptInjectionError(
                "Prompt injection detected",
                matched_patterns=scan_result["matched_patterns"],
            )

        # 对于 warn 级别，进行简单清理
        if scan_result["action"] == "warn":
            sanitized = text
            for pattern in scan_result["matched_patterns"]:
                sanitized = sanitized.replace(pattern, "[REMOVED]")
            logger.info("Prompt sanitized", original_length=len(text), sanitized_length=len(sanitized))
            return sanitized

        return text


class PromptInjectionError(Exception):
    """Prompt 注入错误"""

    def __init__(self, message: str, matched_patterns: list[str]):
        self.message = message
        self.matched_patterns = matched_patterns
        super().__init__(message)


# 全局实例
prompt_guard = PromptInjectionGuard()