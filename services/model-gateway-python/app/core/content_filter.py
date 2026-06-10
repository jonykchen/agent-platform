"""内容安全过滤

在模型调用前对用户输入做本地敏感内容预检（前置过滤），命中则直接拒绝，
避免将违规内容发往 Provider，同时降低合规风险。命中时抛出
ModelContentFilteredError，由 API 层转为标准错误响应。

【设计说明】
- 本地词表为第一道防线（低延迟、可离线），生产可叠加 Provider 侧安全策略
- 词表通过配置可扩展；默认包含基础违规类目占位词，避免硬编码大量敏感词
- 命中记录用于合规审计（仅记录类目与命中位置，不回显完整违规内容）
"""

import re

import structlog

from app.core.exceptions import ModelContentFilteredError

logger = structlog.get_logger()


class ContentFilter:
    """本地敏感内容过滤器

    采用分类词表 + 正则匹配。词表可经构造参数扩展（生产环境从配置/远端加载）。
    """

    # 默认敏感词类目（占位基础词，生产环境应从配置中心加载完整词库）
    DEFAULT_BLOCKLIST: dict[str, list[str]] = {
        "violence": ["制造炸弹", "制作炸药", "枪支制造"],
        "illegal": ["贩毒", "洗钱教程", "伪造证件"],
        "self_harm": ["自杀方法", "自残教程"],
    }

    def __init__(self, blocklist: dict[str, list[str]] | None = None, enabled: bool = True):
        self.enabled = enabled
        blocklist = blocklist or self.DEFAULT_BLOCKLIST
        # 预编译每个类目的匹配正则（任一词命中即匹配）
        self._patterns: dict[str, re.Pattern] = {}
        for category, words in blocklist.items():
            terms = [re.escape(w) for w in words if w]
            if terms:
                self._patterns[category] = re.compile("|".join(terms))

    def scan(self, text: str) -> tuple[bool, str | None]:
        """扫描文本是否命中敏感内容。

        Returns:
            (是否命中, 命中类目)；未命中返回 (False, None)
        """
        if not self.enabled or not text:
            return False, None
        for category, pattern in self._patterns.items():
            if pattern.search(text):
                return True, category
        return False, None

    def check_messages(self, messages: list[dict], request_id: str = "") -> None:
        """检查消息列表中的用户输入，命中则抛出 ModelContentFilteredError。

        Args:
            messages: OpenAI 格式消息列表
            request_id: 请求 ID（用于审计日志）

        Raises:
            ModelContentFilteredError: 命中敏感内容
        """
        if not self.enabled:
            return
        for msg in messages:
            if msg.get("role") != "user":
                continue
            hit, category = self.scan(msg.get("content", ""))
            if hit:
                # 合规审计：仅记录类目，不回显完整违规内容
                logger.warning(
                    "content_filtered",
                    request_id=request_id,
                    category=category,
                    action="rejected",
                )
                raise ModelContentFilteredError(reason=f"输入命中敏感内容类目: {category}")


_content_filter: ContentFilter | None = None


def get_content_filter() -> ContentFilter:
    """获取全局内容过滤器单例"""
    global _content_filter
    if _content_filter is None:
        try:
            from app.core.config import config

            enabled = getattr(config, "content_filter_enabled", True)
        except Exception:
            enabled = True
        _content_filter = ContentFilter(enabled=enabled)
    return _content_filter
