"""重排序器

使用 Cross-Encoder 对检索结果进行精排。
"""

import structlog

logger = structlog.get_logger()


class Reranker:
    """重排序器"""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or "cross-encoder"
        self._model = None

    async def _load_model(self):
        """加载模型（延迟加载）"""
        if self._model is None:
            # TODO: 加载真实的 Cross-Encoder 模型
            # 当前使用 Mock 实现
            logger.info("Reranker initialized (mock)")
            self._model = "mock"

    async def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int | None = None,
    ) -> list[dict]:
        """重排序

        Args:
            query: 查询文本
            results: 检索结果列表
            top_k: 返回数量

        Returns:
            重排序后的结果
        """
        await self._load_model()

        if self._model == "mock":
            return self._mock_rerank(query, results, top_k)

        # TODO: 实现真实的 Cross-Encoder 重排序
        return results[:top_k] if top_k else results

    def _mock_rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int | None,
    ) -> list[dict]:
        """Mock 重排序

        简化实现：基于内容与查询的词重叠度排序。
        """
        query_terms = set(query.lower().split())

        scored_results = []
        for r in results:
            content = r.get("content", "").lower()
            content_terms = set(content.split())

            # 计算词重叠度
            overlap = len(query_terms & content_terms)
            overlap_ratio = overlap / len(query_terms) if query_terms else 0

            scored_results.append({
                **r,
                "rerank_score": overlap_ratio,
                "source": "reranked",
            })

        # 按重排序分数排序
        sorted_results = sorted(scored_results, key=lambda x: x["rerank_score"], reverse=True)

        return sorted_results[:top_k] if top_k else sorted_results

    async def score_pair(self, query: str, content: str) -> float:
        """计算单个 query-content 的相关性分数"""
        await self._load_model()

        if self._model == "mock":
            # Mock: 计算词重叠度
            query_terms = set(query.lower().split())
            content_terms = set(content.lower().split())
            overlap = len(query_terms & content_terms)
            return overlap / len(query_terms) if query_terms else 0.0

        # TODO: 实现真实的 Cross-Encoder 分数计算
        return 0.0


# 全局实例
_reranker = None


def get_reranker() -> Reranker:
    """获取重排序器实例"""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker