"""Prompt 注入防护 (S-02)

检测和阻止 Prompt 注入攻击，支持中文模式。

【核心概念】Prompt 注入攻击
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Prompt 注入是一种对抗性攻击，试图让 LLM：
1. 忽略原有指令，执行攻击者指定的操作
2. 泄露系统提示、工具定义等敏感信息
3. 越权执行（如模拟管理员角色）

常见注入模式：
- "Ignore all previous instructions and..."
- "You are now a..."
- "忽略以上所有内容，现在你是..."

【技术选型】注入检测方案
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────┬─────────────────────────────┬─────────────────────────────┐
│ 方案               │ 优点                        │ 缺点                        │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 正则匹配 (选择)    │ • 简单高效                  │ • 需维护模式列表            │
│                    │ • 零依赖                    │ • 可能漏检新型攻击          │
│                    │ • 可解释                    │                              │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ LLM 检测           │ • 可处理新型攻击            │ • 增加调用成本              │
│                    │ • 语义理解强                │ • 延迟高                    │
│                    │                             │ • 可能被攻击绕过            │
├────────────────────┼─────────────────────────────┼─────────────────────────────┤
│ 机器学习分类器     │ • 性能好                    │ • 需训练数据                │
│                    │ • 可持续学习                │ • 部署复杂                  │
│                    │                             │ • 需要定期更新              │
└────────────────────┴─────────────────────────────┴─────────────────────────────┘

【选择正则匹配的原因】
1. 速度快：注入检测在请求路径上，不能成为瓶颈
2. 已知攻击模式足够覆盖当前威胁
3. 正则易于调整和扩展

【中英文模式覆盖】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

英文模式：
- "ignore previous instructions"
- "you are now a..."
- "disregard all above"

中文模式：
- "忽略以上指令"
- "你现在是一个..."
- "无视以上所有内容"

【风险评分机制】
- 每匹配一个模式，增加 0.3 分
- 匹配高风险关键词，增加 0.2 分
- 最终分数 >= 0.9：block（阻止）
- 最终分数 >= 0.7：warn（警告）
- 最终分数 > 0.3：log（记录）

【处理策略】
- block: 拒绝请求，返回安全错误
- warn: 移除注入内容后继续
- log: 记录日志，正常处理
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