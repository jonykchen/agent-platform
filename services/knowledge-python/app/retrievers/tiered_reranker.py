"""分层重排序器

【核心概念】分层 Rerank
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

检索系统采用两阶段架构：
1. 第一阶段（粗排）：快速召回大量候选（BM25 + 向量），取 Top-50
2. 第二阶段（精排）：Cross-Encoder 精细重排，取 Top-10

【为什么分层？】
┌─────────────────────────────────────────────────────────────────────────┐
│  指标              │  BM25        │  向量检索     │  Cross-Encoder    │
├──────────────────┼─────────────┼──────────────┼───────────────────┤
│  延迟             │  ~5ms       │  ~50ms       │  ~200ms (50个)   │
│  召回率           │  高（关键词）│  高（语义）   │  最高（精细）     │
│  计算成本         │  极低        │  低          │  较高             │
└─────────────────────────────────────────────────────────────────────────┘

分层设计平衡了延迟和质量：
- 粗排阶段快速召回，覆盖足够候选
- 精排阶段只在少量候选上计算，控制成本

【融合策略】
第一层粗排使用 BM25 + Cosine 融合：
- score = alpha * cosine_score + (1 - alpha) * bm25_score
- alpha 默认 0.7（偏重语义匹配）

【参考】
- BGE Reranker: https://huggingface.co/BAAI/bge-reranker-base
- Rerank 论文: https://arxiv.org/abs/2109.07455
"""

from __future__ import annotations

import asyncio
import structlog
from typing import Any

from app.retrievers.reranker import Reranker, get_reranker
from app.core.config import config

logger = structlog.get_logger()

# 粗排默认候选数量
COARSE_TOP_K = 50
# 精排默认结果数量
FINE_TOP_K = 10


class TieredReranker:
    """分层重排序器

    架构：
    ┌─────────────────────────────────────────────────────────────────────┐
    │  输入：混合检索结果（BM25 + 向量）约 100-200 条                      │
    │                                                                     │
    │  第一层：粗排（BM25 + Cosine 融合）→ Top-50                         │
    │                                                                     │
    │  第二层：精排（Cross-Encoder）→ Top-10                             │
    │                                                                     │
    │  输出：重排序后的结果列表                                            │
    └─────────────────────────────────────────────────────────────────────┘

    使用示例：
        reranker = TieredReranker()

        # 输入混合检索结果
        results = await hybrid_retriever.search(query)
        # 执行分层重排
        reranked = await reranker.rerank(query, results, top_k=10)
    """

    def __init__(
        self,
        coarse_top_k: int = COARSE_TOP_K,
        fine_top_k: int = FINE_TOP_K,
        alpha: float = 0.7,  # 向量权重
        cross_encoder_model: str | None = None,
    ):
        """初始化分层重排序器

        Args:
            coarse_top_k: 粗排候选数量
            fine_top_k: 精排结果数量
            alpha: 粗排融合时向量检索权重（1-alpha 为 BM25 权重）
            cross_encoder_model: Cross-Encoder 模型名称
        """
        self.coarse_top_k = coarse_top_k
        self.fine_top_k = fine_top_k
        self.alpha = alpha
        self.cross_encoder_model = cross_encoder_model
        self._fine_reranker: Reranker | None = None

    async def _get_fine_reranker(self) -> Reranker:
        """获取精排重排序器"""
        if self._fine_reranker is None:
            self._fine_reranker = get_reranker()
        return self._fine_reranker

    async def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """执行分层重排序

        流程：
        1. 第一层粗排：BM25 + Cosine 融合
        2. 第二层精排：Cross-Encoder

        Args:
            query: 查询文本
            results: 检索结果列表（包含 score 和 source 字段）
            top_k: 最终返回数量

        Returns:
            重排序后的结果列表
        """
        if not results:
            return []

        top_k = top_k or self.fine_top_k

        # 分离向量检索和关键词检索结果
        vector_results = [r for r in results if r.get("source") == "vector"]
        keyword_results = [r for r in results if r.get("source") == "keyword"]
        hybrid_results = [r for r in results if r.get("source") == "hybrid"]

        # 如果已经是混合结果，跳过粗排
        if hybrid_results:
            # 直接使用原结果进行精排
            coarse_results = results[:self.coarse_top_k]
        else:
            # 执行第一层粗排
            coarse_results = self._coarse_rank(
                vector_results, keyword_results
            )

        logger.debug(
            "tiered_rerank_coarse",
            vector_count=len(vector_results),
            keyword_count=len(keyword_results),
            coarse_count=len(coarse_results),
        )

        # 执行第二层精排
        try:
            fine_reranker = await self._get_fine_reranker()
            fine_results = await fine_reranker.rerank(
                query, coarse_results, top_k=top_k
            )

            logger.info(
                "tiered_rerank_complete",
                input_count=len(results),
                output_count=len(fine_results),
            )

            return fine_results

        except Exception as e:
            logger.warning(
                "tiered_rerank_fine_failed",
                error=str(e),
                fallback_to_coarse=True,
            )
            # 降级：直接返回粗排结果
            return coarse_results[:top_k]

    def _coarse_rank(
        self,
        vector_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """第一层粗排：BM25 + Cosine 融合

        融合公式：
        score = alpha * cosine_score + (1 - alpha) * bm25_score

        归一化：
        - Cosine 分数已经归一化（0-1）
        - BM25 分数需要归一化（除以最大值）

        Args:
            vector_results: 向量检索结果
            keyword_results: BM25 检索结果

        Returns:
            粗排后的结果列表
        """
        # 构建 chunk_id -> result 映射
        merged: dict[str, dict[str, Any]] = {}

        # 处理向量检索结果
        for r in vector_results:
            chunk_id = r.get("chunk_id")
            if not chunk_id:
                continue

            merged[chunk_id] = {
                **r,
                "vector_score": r.get("score", 0),
                "keyword_score": 0,
                "source": "coarse",
            }

        # 处理 BM25 结果
        max_bm25 = 0
        for r in keyword_results:
            chunk_id = r.get("chunk_id")
            if not chunk_id:
                continue

            score = r.get("score", 0)
            max_bm25 = max(max_bm25, score)

            if chunk_id in merged:
                merged[chunk_id]["keyword_score"] = score
            else:
                merged[chunk_id] = {
                    **r,
                    "vector_score": 0,
                    "keyword_score": score,
                    "source": "coarse",
                }

        # 归一化 BM25 分数并计算融合分数
        for chunk_id, data in merged.items():
            # 归一化 BM25 分数
            norm_keyword = data["keyword_score"] / max_bm25 if max_bm25 > 0 else 0

            # 融合分数
            data["coarse_score"] = (
                self.alpha * data["vector_score"]
                + (1 - self.alpha) * norm_keyword
            )
            data["score"] = data["coarse_score"]

        # 按融合分数排序
        sorted_results = sorted(
            merged.values(),
            key=lambda x: x["coarse_score"],
            reverse=True,
        )

        return sorted_results[:self.coarse_top_k]

    async def batch_rerank(
        self,
        query_results_pairs: list[tuple[str, list[dict]]],
        top_k: int | None = None,
    ) -> list[list[dict[str, Any]]]:
        """批量重排序

        Args:
            query_results_pairs: (query, results) 元组列表
            top_k: 每组返回数量

        Returns:
            重排序结果列表
        """
        tasks = [
            self.rerank(query, results, top_k)
            for query, results in query_results_pairs
        ]
        return await asyncio.gather(*tasks)


# 全局实例
_tiered_reranker: TieredReranker | None = None


def get_tiered_reranker(
    coarse_top_k: int | None = None,
    fine_top_k: int | None = None,
) -> TieredReranker:
    """获取分层重排序器实例

    Args:
        coarse_top_k: 粗排候选数量（可选，用于自定义配置）
        fine_top_k: 精排结果数量（可选）

    Returns:
        TieredReranker 实例
    """
    global _tiered_reranker
    if _tiered_reranker is None:
        _tiered_reranker = TieredReranker(
            coarse_top_k=coarse_top_k or config.rerank_top_k,
            fine_top_k=fine_top_k or config.default_top_k,
        )
    return _tiered_reranker
