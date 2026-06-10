"""重排序器 - Cross-Encoder 实现

【核心概念】Cross-Encoder 重排序
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

检索系统通常采用两阶段架构：
1. 第一阶段：快速检索（BM25/向量检索），召回大量候选
2. 第二阶段：精细重排序（Cross-Encoder），精选 Top-K

【Cross-Encoder vs Bi-Encoder】
┌─────────────────────────────────────────────────────────────────────────┐
│  方案              │  优点                    │  缺点                  │
├────────────────────┼──────────────────────────┼────────────────────────┤
│  Bi-Encoder       │  快速（向量预计算）       │  精度较低（独立编码）  │
│  Cross-Encoder    │  精度高（联合编码）       │  较慢（实时计算）      │
└─────────────────────────────────────────────────────────────────────────┘

Cross-Encoder 同时编码 query 和 document，能捕捉细粒度语义关系。
适合对 Bi-Encoder 检索结果进行精细重排序。

【模型选择】
- 小模型：bge-reranker-base（速度快，适合在线）
- 大模型：bge-reranker-large（精度高，适合离线）

【参考】
- BGE Reranker: https://huggingface.co/BAAI/bge-reranker-base
- Cross-Encoder 介绍: https://www.sbert.net/examples/applications/cross-encoder/
"""

from __future__ import annotations

import httpx
import structlog

from app.core.config import config

logger = structlog.get_logger()


class Reranker:
    """Cross-Encoder 重排序器

    采用 API 调用模式：调用远程 rerank 服务（bge-reranker 等），
    避免本地加载大模型与引入 torch/sentence-transformers 等重依赖。
    远程不可用时降级为词重叠打分（_fallback_rerank）。
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_url: str | None = None,
    ):
        self.model_name = model_name or config.embedding_model
        self.api_url = api_url or config.embedding_service_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.api_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int | None = None,
    ) -> list[dict]:
        """重排序检索结果

        【处理流程】
        1. 构建 query-document pairs
        2. 批量计算相关性分数
        3. 按分数排序
        4. 返回 Top-K

        Args:
            query: 查询文本
            results: 检索结果列表（每个包含 content 字段）
            top_k: 返回数量（默认返回全部）

        Returns:
            重排序后的结果列表（包含 rerank_score 字段）
        """
        if not results:
            return []

        top_k = top_k or len(results)

        # 构建输入
        documents = [r.get("content", "") for r in results]

        try:
            # 调用 API
            scores = await self._rerank_batch(query, documents)

            # 添加分数并排序
            scored_results = []
            for i, r in enumerate(results):
                scored_results.append(
                    {
                        **r,
                        "rerank_score": scores[i],
                        "source": "reranked",
                    }
                )

            # 按分数降序排序
            sorted_results = sorted(
                scored_results,
                key=lambda x: x["rerank_score"],
                reverse=True,
            )

            return sorted_results[:top_k]

        except Exception as e:
            logger.warning(
                "rerank_api_failed",
                query=query[:50],
                error=str(e),
            )
            # 降级：使用 Mock 实现
            return self._fallback_rerank(query, results, top_k)

    async def _rerank_batch(
        self,
        query: str,
        documents: list[str],
    ) -> list[float]:
        """批量计算重排序分数

        Args:
            query: 查询文本
            documents: 文档列表

        Returns:
            分数列表（0-1）
        """
        client = await self._get_client()

        # 构建 rerank 请求
        payload = {
            "model": "bge-reranker-base",
            "query": query,
            "documents": documents,
            "top_k": len(documents),
        }

        response = await client.post("/v1/rerank", json=payload)
        response.raise_for_status()

        data = response.json()

        # 解析结果（按 index 排序）
        results = sorted(data.get("results", []), key=lambda x: x.get("index", 0))

        return [r.get("relevance_score", 0.0) for r in results]

    def _fallback_rerank(
        self,
        query: str,
        results: list[dict],
        top_k: int,
    ) -> list[dict]:
        """降级重排序（基于词重叠）"""
        query_terms = set(query.lower().split())

        scored_results = []
        for r in results:
            content = r.get("content", "").lower()
            content_terms = set(content.split())

            overlap = len(query_terms & content_terms)
            overlap_ratio = overlap / len(query_terms) if query_terms else 0

            scored_results.append(
                {
                    **r,
                    "rerank_score": overlap_ratio,
                    "source": "fallback_reranked",
                }
            )

        sorted_results = sorted(
            scored_results,
            key=lambda x: x["rerank_score"],
            reverse=True,
        )

        return sorted_results[:top_k]

    async def score_pair(self, query: str, content: str) -> float:
        """计算单个 query-content 的相关性分数

        Args:
            query: 查询文本
            content: 文档内容

        Returns:
            相关性分数（0-1）
        """
        scores = await self._rerank_batch(query, [content])
        return scores[0] if scores else 0.0


# 全局实例
_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """获取重排序器实例"""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
